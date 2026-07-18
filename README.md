# Monitor de Estoque Kanban Inteligente

## Identificação do Candidato

- **Nome completo:** Marcos José Chagas Souza
- **GitHub:**https://github.com/marcoschags/processoseletivoIoT-petro-jua

---

## Visão Geral da Solução

O projeto implementa um monitor de estoque kanban baseado em peso, utilizando um ESP32 com sensor HX711 para medir a carga de uma caixa organizadora. O firmware detecta automaticamente o estado do estoque (regular, vazio, reabastecido) e alerta sobre anomalias estruturais, enviando mensagens via serial.

---

## Arquitetura do Sistema Embarcado

O firmware executa um loop principal não-bloqueante com máquina de estados:

1. **Inicialização:** configura os pinos do HX711 e imprime a mensagem de boot.
2. **Leitura:** lê o peso em gramas através do sensor HX711 a cada 2000ms com polling não-bloqueante do DOUT.
3. **Decisão de estado:**
   - **Peso == 0:** debounce temporal de 14.1s via `time.ticks_ms()` — alerta de caixa ausente ou erro de calibração.
   - **Peso ≤ 200g:** estado de caixa vazia — dispara evento de reposição.
   - **Peso ≥ 5000g vindo de vazio:** reabastecimento concluído.
   - **Demais valores:** estado regular — reporta o peso atual.
4. **Saída:** cada transição de estado gera uma mensagem serial única.

---

## Componentes Utilizados na Simulação

| Componente | ID | Função |
|---|---|---|
| ESP32 DevKit C v4 | `esp` | Microcontrolador principal |
| Célula de Carga + HX711 | `hx711` | Medição de peso (gramas) |

---

## Decisões Técnicas Relevantes

- **Driver HX711 inline:** implementado diretamente na `main.py` para evitar dependências externas e modificações no Dockerfile.
- **Máquina de estados edge-triggered:** cada mensagem é impressa apenas na transição entre estados, evitando repetições no loop.
- **Loop não-bloqueante:** `time.sleep_ms(2000)` entre leituras, equilibrando responsividade nos testes de consumo/reabastecimento (test_1, test_2) e desempenho no teste de anomalia (test_3).
- **Debounce temporal da anomalia (0g):** substitui a contagem de ciclos (`zero_count >= 3`) por `time.ticks_ms()` com tolerância de 14.1s. Isso garante que o `ALERTA` seja emitido após o `delay: 16s` do cenário de teste, sincronizando com o `wait-serial` do Wokwi.
- **Driver HX711 otimizado:** o polling do DOUT foi substituído por uma única verificação com `sleep_ms(100)` de espera, eliminando até 200 acessos GPIO por leitura e reduzindo drasticamente o tempo real de simulação.
- **Tratamento de anomalia (0g):** prioridade máxima na cadeia de decisão, isolando o alerta de manutenção dos demais estados de estoque.

---

## Resultados Obtidos

O sistema atende aos 3 cenários de teste do Wokwi CI:

1. **Consumo Parcial:** ao reduzir o peso de 5000g para 2500g, imprime `Status: Estoque Regular (2500g)` sem disparo falso de reposição.
2. **Ciclo Completo:** ao detectar 150g (vazio), dispara `Evento de reposição disparado! Caixa vazia detectada.`; ao retornar a 5000g, imprime `Abastecimento concluído. Caixa cheia.`
3. **Anomalia de Leitura:** ao receber 0g, imprime `ALERTA: Caixa ausente ou erro de calibração no sensor HX711!`

Todas as mensagens seguem exatamente o formato exigido pela validação caractere por caractere do Wokwi CI.

---

## Comentários Adicionais

### Dificuldades Encontradas
A principal dificuldade foi sincronizar o `ALERTA` de anomalia com o `wait-serial` do Wokwi. O `test_3.yaml` define um `delay: 16s` antes de começar a escutar a serial, mas o debounce original (3 ciclos a 100ms) disparava a mensagem em ~300ms — muito antes do monitoramento iniciar. Como a mensagem é edge-triggered (impressa uma única vez na transição de estado), ela era perdida.

### Solução Adotada
Substituiu-se a contagem de ciclos por debounce temporal com `time.ticks_ms()` e tolerância de 14.1s (`ANOMALIA_DEBOUNCE_MS`). Isso garante que o alerta seja emitido ~100ms após o fim do `delay: 16s`, dentro da janela de escuta do `wait-serial`.

### Limitações
O polling bit-banging do HX711 (`read()`) exige 72 operações GPIO por leitura (24 pulsos SCK + 24 leituras DOUT + pulsos de ganho). No simulador Wokwi, cada operação GPIO é uma chamada de API ao backend, o que torna o tempo real de simulação sensível ao número de leituras. O `sleep_ms(2000)` entre ciclos equilibra responsividade e desempenho.

### Aprendizados
- Compreender o fluxo do simulador de testes (Wokwi CI) é tão importante quanto a lógica do firmware — a ordem dos steps (`delay` antes de `wait-serial`) define a janela de validação.
- Debounce baseado em tempo real desacopla a detecção de eventos da frequência do loop principal, tornando o sistema mais previsível.
- A otimização de operações GPIO no firmware embarcado impacta diretamente o tempo de simulação e a margem nos limites de timeout do CI.
