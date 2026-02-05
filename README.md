# z.ai Conversation for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![GitHub release](https://img.shields.io/github/v/release/iannuz92/zai-conversation-ha)](https://github.com/iannuz92/zai-conversation-ha/releases)

Integrazione custom per Home Assistant che trasforma i modelli GLM-4 di z.ai in un vero **assistente personale domotico**. Basata sul pattern dell'integrazione ufficiale Anthropic, con supporto completo al function calling, personalità configurabile, memoria persistente e contesto automatico dei dispositivi.

## ✨ Funzionalità

### Core
- 🤖 **Modelli GLM-4** — Supporto per glm-4.7, glm-4-flash, glm-4-plus, glm-4-air, glm-4-airx, glm-4-long
- 🏠 **Controllo dispositivi** — Comandi vocali/testuali con function calling nativo HA
- 🔧 **Conversation Agent** — Integrazione completa con il sistema Assist di Home Assistant

### Assistente Personale
- 🧠 **Memoria persistente** — Ricorda le tue preferenze, note e contesto tra le sessioni
- 🎭 **Personalità configurabile** — Scegli tra Formale, Amichevole o Conciso
- 📍 **Contesto dispositivi** — Il LLM riceve automaticamente lo stato reale di luci, sensori, termostati, tapparelle raggruppati per area
- 🎯 **Filtro per area** — Limita il contesto solo alle aree che ti interessano
- 📝 **Prompt personalizzabile** — Istruzioni extra per personalizzare il comportamento

## 📦 Installazione

### HACS (Consigliato)

1. Apri **HACS** in Home Assistant
2. Vai su **Integrazioni**
3. Clicca i tre puntini in alto a destra → **Repository personalizzati**
4. Aggiungi: `https://github.com/iannuz92/zai-conversation-ha`
5. Categoria: **Integrazione**
6. Clicca **Aggiungi**
7. Cerca "z.ai Conversation" e installala
8. **Riavvia Home Assistant**

### Installazione Manuale

1. Copia la cartella `custom_components/zai_conversation` nella directory `custom_components` di Home Assistant
2. Riavvia Home Assistant

## ⚙️ Configurazione

### Ottenere la API Key

1. Vai su [z.ai](https://z.ai) e crea un account
2. Vai nelle impostazioni API
3. Genera una nuova API key

### Setup dell'Integrazione

1. **Impostazioni** → **Dispositivi e Servizi** → **+ Aggiungi Integrazione**
2. Cerca **"z.ai Conversation"**
3. Inserisci:
   - **API Key**: la tua chiave API z.ai
   - **Base URL**: `https://api.z.ai/api/anthropic` (default)
4. Clicca **Invia** — verrà effettuato un test di connessione

### Opzioni di Configurazione

Dopo l'installazione, clicca **Configura** sull'integrazione:

#### Opzioni Base

| Opzione | Descrizione | Default |
|---------|-------------|---------|
| **Personalità** | Stile delle risposte (Formale / Amichevole / Conciso) | Amichevole |
| **Memoria** | Abilita memoria persistente tra le sessioni | ✅ Attiva |
| **Prompt ottimizzato** | Usa il prompt avanzato con contesto dispositivi | ✅ Attivo |
| **Istruzioni extra** | Template aggiuntivo per personalizzare il comportamento | — |
| **Controllo HA** | API per il controllo dispositivi (`assist` / `intent` / `none`) | `assist` |
| **Impostazioni consigliate** | Usa parametri ottimizzati per il modello | ✅ Attivo |

#### Opzioni Avanzate (disabilita "Impostazioni consigliate")

| Opzione | Descrizione | Default | Range |
|---------|-------------|---------|-------|
| **Modello** | Modello GLM-4 da usare | glm-4.7 | Vedi tabella |
| **Token massimi** | Lunghezza massima risposta | 3000 | 1–8000 |
| **Temperatura** | Creatività delle risposte | 0.7 | 0–1 |
| **Filtro aree** | Limita il contesto ai dispositivi di aree specifiche | Tutte | Multi-select |

## 🚀 Utilizzo

### Comandi Naturali

Con "Controllo Home Assistant" impostato su `assist`:

```
"Accendi le luci del soggiorno"
"Imposta il termostato a 22 gradi"
"Che temperatura c'è in camera da letto?"
"Chiudi tutte le tapparelle"
"Metti la luce della cucina al 50%"
"Spegni tutto in camera"
```

### Memoria dell'Assistente

L'assistente ricorda le tue preferenze tra una sessione e l'altra:

```
"Ricorda che preferisco le luci calde la sera"
"La mia temperatura ideale è 21 gradi"
"Annota che domani devo chiamare l'idraulico"
```

### Personalità

| Personalità | Stile |
|-------------|-------|
| **Formale** | Professionale, preciso, usa il "Lei" |
| **Amichevole** | Colloquiale, con emoji, usa il "tu" |
| **Conciso** | Risposte minimali, solo l'essenziale |

## 📋 Modelli Supportati

| Modello | Descrizione | Consigliato per |
|---------|-------------|-----------------|
| `glm-4.7` | Modello principale, bilanciato | ⭐ Uso generale |
| `glm-4-flash` | Veloce, risposte rapide | Automazioni veloci |
| `glm-4-plus` | Più potente | Conversazioni complesse |
| `glm-4-air` | Leggero | Risposte semplici |
| `glm-4-airx` | Air ottimizzato | Performance |
| `glm-4-long` | Contesto esteso | Conversazioni lunghe |

## 🏗️ Architettura

```
custom_components/zai_conversation/
├── __init__.py            # Entry point, setup client e memoria
├── conversation.py        # Entity principale, gestione chat e API
├── config_flow.py         # Flusso di configurazione UI
├── const.py               # Costanti e default
├── entity.py              # Entity base
├── device_manager.py      # Builder contesto dispositivi per area
├── assistant_memory.py    # Memoria persistente JSON
├── prompt_templates.py    # Template personalità e istruzioni
├── manifest.json
├── strings.json
└── translations/
    └── en.json
```

### Come Funziona

1. **`conversation.py`** riceve il messaggio dall'utente via Assist
2. **`device_manager.py`** raccoglie lo stato di tutti i dispositivi raggruppati per area
3. **`prompt_templates.py`** costruisce il system prompt con personalità + contesto dispositivi + memoria
4. **`assistant_memory.py`** inietta le preferenze e note memorizzate
5. Il prompt completo viene inviato insieme alle istruzioni di Home Assistant (tool calling) all'API z.ai
6. La risposta viene processata: se contiene tool calls, vengono eseguite e il risultato reinviato al modello fino a 10 iterazioni

## 🔧 Troubleshooting

### Errore "Cannot connect"
- Verifica che la API key sia corretta
- Controlla la connessione internet
- Verifica il Base URL
- Controlla i log di HA: **Impostazioni** → **Sistema** → **Log**

### Errore "Authentication error"
- La API key potrebbe essere scaduta
- Genera una nuova key da z.ai
- Riconfigura l'integrazione

### L'agente non risponde
- Controlla i log di HA per errori dettagliati
- Verifica che l'agente conversazione sia abilitato in Assist
- Prova a ridurre i token massimi
- Verifica che il servizio z.ai sia operativo

### Il controllo dispositivi non funziona
- Assicurati che "Controllo Home Assistant" sia impostato su `assist`
- Verifica che i dispositivi siano correttamente configurati in HA
- Controlla i log per problemi di permessi
- Prova a disabilitare il filtro aree per includere tutti i dispositivi

### L'assistente non ricorda le preferenze
- Verifica che la memoria sia abilitata nelle opzioni
- La memoria viene salvata in `/.storage/zai_memory_<entry_id>.json`
- Riavvia HA se la memoria non si carica

## 📋 Requisiti

- **Home Assistant** 2024.1.0 o successivo
- **Python** 3.12+ (fornito dall'installazione HA)
- **Pacchetto** `anthropic` v0.40.0 (installato automaticamente)
- **Account** [z.ai](https://z.ai) con API key attiva

## 🤝 Supporto

- 🐛 [Apri un issue](https://github.com/iannuz92/zai-conversation-ha/issues) per bug o richieste
- 📋 Includi i log di Home Assistant quando segnali problemi
- 💡 Le pull request sono benvenute

## 📜 Crediti

Basata sull'integrazione ufficiale [Anthropic](https://github.com/home-assistant/core/tree/dev/homeassistant/components/anthropic) di Home Assistant core, adattata per l'API z.ai con funzionalità avanzate di assistente personale.

## 📄 Licenza

MIT License — Vedi il file [LICENSE](LICENSE) per i dettagli.

---

## Changelog

### v1.0.2

- 🐛 Fix critico: accesso al system prompt tramite `chat_log.content[0]` (SystemContent)
- 🐛 Fix: messaggi API ora escludono correttamente il SystemContent (`content[1:]`)
- 🐛 Fix: gestione attributi tool_call compatibile con `llm.ToolInput`
- 🐛 Fix: aggiunto handling `ConverseError` su `async_provide_llm_data`
- 🐛 Fix: rimossa ereditarietà `ZaiBaseLLMEntity` incompatibile
- 🐛 Fix: rimosso `isinstance()` con TypeAliasType (crash su Python 3.12+)
- 🧹 Pulizia import inutilizzati in tutti i moduli

### v1.0.1

- 🐛 Fix errori di indentazione in `config_flow.py` e `conversation.py`
- 🐛 Fix gestione errori robusta con fallback

### v1.0.0

- 🎉 Release iniziale
- 🤖 Supporto modelli GLM-4 via z.ai
- 🏠 Conversation agent con function calling
- 🧠 Memoria persistente dell'assistente
- 🎭 Personalità configurabili (Formale/Amichevole/Conciso)
- 📍 Contesto automatico dispositivi per area
- ⚙️ Configurazione completa da UI
- 📦 Compatibilità HACS
