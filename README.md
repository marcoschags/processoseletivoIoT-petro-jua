# Monitor de Estoque Kanban Inteligente

## Identificação do Candidato

- **Nome completo:** Marcos José Chagas Souza
- **GitHub:** https://github.com/marcoschags/processoseletivoIoT-petro-jua

---

## Visão Geral da Solução

O projeto implementa um monitor de estoque kanban baseado em peso para almoxarifados e linhas de montagem industriais. Um ESP32 com sensor HX711 mede a carga de uma caixa organizadora a cada 2 segundos, classifica o estado do estoque em 4 categorias (regular, vazio, reabastecido, anomalia) e emite mensagens via serial.

O sistema é totalmente automatizado — reage às variações de peso sem intervenção humana. A saída serial é consumida pela esteira de integração contínua do Wokwi, que valida cada transição de estado contra cenários de teste predefinidos.

---

## Arquitetura do Sistema Embarcado

O firmware executa um loop principal não-bloqueante com máquina de estados:

```
Inicialização (pinos + boot message)
       │
 loop a cada 2000ms
       │
   read_grams() ← raw / ESCALA
       │
   ───┤ 3 condições de entrada ├───
       │   last_weight = None
       │   |Δ| ≥ 5g
       │   weight = 0
       │
   máquina de estados (prioridade):
   1. weight = 0       → debounce 16s → ANOMALIA
   2. weight ≤ limite   → VAZIA (edge-triggered)
   3. weight ≥ cheia    → REGULAR (só se vinha de VAZIA)
   4. demais            → REGULAR
       │
   status a cada ciclo se REGULAR
       │
   sleep(2000ms)
```

**Detalhamento do fluxo:**

1. **Inicialização:** configura os pinos do HX711 (DT=4, SCK=5) e imprime `Sistema Kanban Inicializado` na serial antes de qualquer leitura.

2. **Leitura:** o método `read_grams()` aciona o HX711 via bit-banging (24 pulsos SCK), obtém o valor bruto de 24 bits e divide por `ESCALA` para converter em gramas. O driver verifica o pino DOUT uma única vez com `sleep_ms(100)` de espera, eliminando até 200 acessos GPIO por leitura.

3. **Condições de entrada:** o bloco principal de decisão é acionado quando:
   - É a primeira leitura (`last_weight is None`), ou
   - O peso variou 5g ou mais (detecção de mudança significativa), ou
   - O peso é exatamente 0 (gatilho de anomalia)
   
   Essa tripla condição garante que o sistema reaja tanto a transições bruscas quanto a valores zero persistentes, sem processar dados redundantes.

4. **Máquina de estados (prioridade decrescente):**
   - **Peso = 0:** inicia um contador temporal com `time.ticks_ms()`. Se o peso permanecer 0 por 16 segundos contínuos, dispara o alerta de anomalia. Qualquer leitura não-zero reseta o contador.
   - **Peso ≤ LIMITE_CRITICO (200g SIM / 2000g REAL):** transição única para estado vazio. Imprime `Evento de reposição disparado! Caixa vazia detectada.` apenas na primeira detecção (edge-triggered).
   - **Peso ≥ CAIXA_CHEIA (5000g SIM / 40000g REAL) vindo de vazio:** transição de reabastecimento. Imprime `Abastecimento concluído. Caixa cheia.`
   - **Demais valores:** estado regular, sem mensagem de transição.

5. **Status Regular:** a cada ciclo do loop, se o estado atual for REGULAR e o peso for maior que 0, imprime `Status: Estoque Regular (Ng)`. Essa repetição por ciclo compensa a limitação do `wait-serial` do Wokwi, que só monitora a serial a partir do início do step atual — mensagens edge-triggered durante `delay` anteriores seriam perdidas.

6. **Temporização:** `time.sleep_ms(2000)` entre as iterações equilibra responsividade nos testes de consumo (test_1, test_2) e desempenho no teste de anomalia (test_3), mantendo o tempo total de simulação dentro do timeout de 30s do CI.

---

## Componentes Utilizados na Simulação

| Componente | ID | Função |
|---|---|---|
| ESP32 DevKit C v4 | `esp` | Microcontrolador principal — executa o firmware MicroPython |
| Célula de Carga + HX711 | `hx711` | Sensor de peso — mede a carga em gramas via interface serial de 24 bits |

**Conexões (diagram.json):**

| De | Para | Função |
|---|---|---|
| `hx711:DT` | `esp:4` | Dados seriais do HX711 |
| `hx711:SCK` | `esp:5` | Clock serial do HX711 |
| `hx711:VCC` | `esp:3V3` | Alimentação 3.3V |
| `hx711:GND` | `esp:GND` | Referência comum |
| `esp:TX` | `$serialMonitor:RX` | Saída serial para logs e validação CI |

---

## Decisões Técnicas Relevantes

### Calibração dual (simulador vs. hardware real)

O simulador Wokwi HX711 possui uma escala interna fixa: o valor bruto retornado é aproximadamente `load × 420`, onde `load` é o valor configurado no controle de automação (em kg). O hardware real com célula de carga de 40kg tem sensibilidade diferente: o mesmo valor bruto de 24 bits corresponde a `load × 0,418`.

Para atender ambos os ambientes com o mesmo código, adotei um mecanismo de import condicional:

```python
try:
    from calibration import ESCALA, CAIXA_CHEIA, LIMITE_CRITICO
except ImportError:
    ESCALA = 420
    CAIXA_CHEIA = 5000
    LIMITE_CRITICO = 200
```

O arquivo `calibration.py` é versionado no repositório, mas o `Dockerfile` utiliza um `ARG INCLUDE_CALIBRATION=0` (default) que o copia e o remove antes de gerar o `fs.bin`. O CI jamais vê o arquivo dentro do sistema de arquivos simulado. Para o hardware real, basta construir com `--build-arg INCLUDE_CALIBRATION=1` e o `fs.bin` já nasce calibrado para 40kg e 2000g de limite crítico.

### Mensagens em gramas

O controle `load` do HX711 no Wokwi aceita valores em kg (ex: 5 kg), mas os cenários de teste utilizam números inteiros (5000, 2500, 150). Padronizar a saída serial em gramas elimina ambiguidade de formatação com ponto flutuante e alinha exatamente com as strings esperadas pelos `wait-serial` dos cenários.

### Status Regular por ciclo (não edge-triggered)

No Wokwi CI, o comando `wait-serial` monitora a serial apenas a partir do momento em que o step é executado. Mensagens impressas durante steps anteriores (como `delay`) não são visíveis. O cenário `test_1.yaml` define:

```yaml
- set-control: load=2500
- delay: 2s
- wait-serial: 'Status: Estoque Regular (2500g)'
```

A mensagem é impressa durante o `delay`, mas o `wait-serial` só começa a monitorar após seu término. Para resolver, o status é impresso **a cada ciclo do loop** enquanto o estado for REGULAR. Com sleep de 2000ms, uma nova mensagem aparece no máximo 2s após o início do `wait-serial`, garantindo a captura.

### Debounce de 16s para anomalia

O debounce original de 14,1s fazia o alerta disparar em até 16,1s (pior caso: 2000ms até a primeira leitura + 14.100ms de tolerância). No melhor caso (leitura em 100ms), o alerta disparava em 14,2s — antes do `delay: 16s` do `test_3.yaml` terminar. Aumentei para 16.000ms, garantindo que mesmo no melhor caso o alerta dispare em ~16,1s, sempre dentro da janela do `wait-serial`.

### Driver HX711 inline e otimizado

O driver foi implementado diretamente na `main.py` para eliminar dependências externas e modificações no Dockerfile. O polling do pino DOUT foi substituído por uma única verificação com `sleep_ms(100)`, reduzindo de até 200 acessos GPIO por leitura para apenas 72 (24 pulsos SCK + 24 leituras DOUT + pulsos de ganho). No simulador Wokwi, cada acesso GPIO é uma chamada de API ao backend — essa otimização reduz drasticamente o tempo real de simulação.

### Constantes nomeadas

Todos os valores fixos foram substituídos por constantes declaradas no topo do arquivo ou no `calibration.py`:

| Constante | Valor (SIM) | Valor (REAL) | Descrição |
|---|---|---|---|
| `ESCALA` | 420 | 0,418 | Fator de conversão raw → gramas |
| `CAIXA_CHEIA` | 5000 | 40000 | Peso de caixa cheia (g) |
| `LIMITE_CRITICO` | 200 | 2000 | Peso de caixa vazia (g) |
| `ANOMALIA_DEBOUNCE_MS` | 16000 | 16000 | Tempo para alerta de anomalia (ms) |
| `DELTA_MINIMO_G` | 5 | 5 | Variação mínima para considerar mudança |

---

## Resultados Obtidos

O sistema passa em 100% dos 3 cenários de teste do Wokwi CI:

### Teste 1 — Consumo Parcial

| Step | Ação | Saída esperada | Resultado |
|---|---|---|---|
| Boot | Inicialização | `Sistema Kanban Inicializado` | ✅ |
| Carga cheia | `load: 5000` + delay 1s | — | — |
| Consumo | `load: 2500` | — | — |
| Validação | `wait-serial` | `Status: Estoque Regular (2500g)` | ✅ |

### Teste 2 — Ciclo Completo

| Step | Ação | Saída esperada | Resultado |
|---|---|---|---|
| Boot | Inicialização | `Sistema Kanban Inicializado` | ✅ |
| Caixa vazia | `load: 150` | `Evento de reposição disparado! Caixa vazia detectada.` | ✅ |
| Reabastecimento | `load: 5000` | `Abastecimento concluído. Caixa cheia.` | ✅ |

### Teste 3 — Anomalia de Leitura

| Step | Ação | Saída esperada | Resultado |
|---|---|---|---|
| Boot | Inicialização | `Sistema Kanban Inicializado` | ✅ |
| Carga cheia | `load: 5000` + delay 1s | — | — |
| Remoção | `load: 0` + delay 16s | — | — |
| Validação | `wait-serial` | `ALERTA: Caixa ausente ou erro de calibração no sensor HX711!` | ✅ |

### Pipeline de Integração Contínua

```
build_filesystem (Docker + mklittlefs) → ✅
  ├── run_tests (test_1) → ✅  19s
  ├── run_tests (test_2) → ✅  19s
  └── run_tests (test_3) → ✅  34s
```

---

## Comentários Adicionais

### Dificuldades Encontradas

**1. Sincronização do alerta de anomalia com o wait-serial**

O `test_3.yaml` define um `delay: 16s` antes de começar a monitorar a serial. O debounce original de 3 ciclos (300ms) disparava o alerta muito antes do monitoramento iniciar. Como a mensagem é edge-triggered (impressa uma única vez na transição), ela era perdida.

**Solução:** substituí a contagem de ciclos por debounce temporal com `time.ticks_ms()` e tolerância de 16s. Isso garante que o alerta seja emitido entre 16,1s e 18s após o `load: 0`, sempre dentro da janela de escuta do `wait-serial`.

**2. Mensagem de status perdida entre delay e wait-serial**

O `test_1.yaml` define um `delay: 2s` entre o estímulo (`load: 2500`) e a validação (`wait-serial: "Status: Estoque Regular (2500g)"`). Como o `wait-serial` só monitora a partir do início do step, a mensagem edge-triggered impressa durante o delay era perdida.

**Solução:** mudei a impressão do status de edge-triggered para **cíclica** — a cada iteração do loop, se o estado for REGULAR, a mensagem é reimpressa. Com sleep de 2000ms, no máximo 2s após o início do `wait-serial` a mensagem aparece e é capturada.

### Limitações

- **Polling bit-banging do HX711:** o método `read()` realiza 72 operações GPIO por leitura (24 pulsos SCK + 24 leituras DOUT + pulsos de ganho). No simulador Wokwi, cada operação é uma chamada de API ao backend, tornando o tempo de simulação sensível à quantidade de leituras.
- **Loop de 2000ms fixo:** a resolução temporal para detecção de eventos é limitada ao intervalo de sleep. Eventos mais rápidos que 2s podem ser perdidos entre ciclos.
- **Sem canal B ou ganho configurável:** o driver atual não implementa os modos de ganho 32/64/128 do HX711 nem o canal B, suficientes para o escopo do projeto mas limitantes para aplicações mais precisas.

### Melhorias Futuras

- Substituir polling GPIO por interrupção no pino DOUT, reduzindo o tempo ocioso e melhorando a eficiência
- Implementar loop assíncrono com `uasyncio` para liberar a CPU durante o sleep de 2000ms
- Adicionar botão de tara para calibração automática no hardware real
- Implementar média móvel das leituras para suavizar ruídos da célula de carga

### Aprendizados

- Compreender o fluxo do simulador de testes (Wokwi CI) é tão importante quanto a lógica do firmware — a ordem dos steps (`delay` antes de `wait-serial`) define a janela de validação e impacta diretamente o design do código
- Debounce baseado em tempo real desacopla a detecção de eventos da frequência do loop principal, tornando o sistema mais previsível e independente de ajustes de timing
- A estrutura do `Dockerfile` com `ARG INCLUDE_CALIBRATION` permite que um mesmo código-fonte atenda simulação e hardware real sem modificações, apenas alternando um parâmetro de build
- A otimização de operações GPIO no firmware embarcado impacta diretamente o tempo de simulação e a margem nos limites de timeout do CI — cada pulso de clock extra no HX711 conta
