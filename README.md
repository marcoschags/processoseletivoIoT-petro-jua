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
2. **Leitura:** lê o peso em gramas através do sensor HX711 a cada 100ms.
3. **Decisão de estado:**
   - **Peso == 0:** estado de anomalia — alerta de caixa ausente ou erro de calibração.
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
- **Loop não-bloqueante:** `time.sleep_ms(100)` entre leituras, sem funções bloqueantes longas, garantindo compatibilidade com o CI do Wokwi.
- **Tratamento de anomalia (0g):** prioridade máxima na cadeia de decisão, isolando o alerta de manutenção dos demais estados de estoque.

---

## Resultados Obtidos

O sistema atende aos 3 cenários de teste do Wokwi CI:

1. **Consumo Parcial:** ao reduzir o peso de 5000g para 2500g, imprime `Status: Estoque Regular (2500g)` sem disparo falso de reposição.
2. **Ciclo Completo:** ao detectar 150g (vazio), dispara `Evento de reposição disparado! Caixa vazia detectada.`; ao retornar a 5000g, imprime `Abastecimento concluído. Caixa cheia.`
3. **Anomalia de Leitura:** ao receber 0g, imprime `ALERTA: Caixa ausente ou erro de calibração no sensor HX711!`

Todas as mensagens seguem exatamente o formato exigido pela validação caractere por caractere do Wokwi CI.
