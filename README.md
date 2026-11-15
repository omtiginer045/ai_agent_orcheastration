# PR Reviewer: Multi-Agent Code Review

Bir pull request diff'ini paralel çalışan uzman AI agent'larına inceleten, sonuçları bir **Judge** agent'ında birleştiren orkestrasyon projesi.

- **Framework:** [Claude Agent SDK](https://code.claude.com/docs/en/agent-sdk) (`claude-agent-sdk`)
- **Orkestrasyon:** Python `asyncio`

## Mimari

```
diff ──► Orchestrator (asyncio)
           ├─► Security agent    ┐
           ├─► Performance agent │  paralel (asyncio.gather)
           ├─► Readability agent │  her biri Read/Grep/Glob ile repoyu okuyabilir
           └─► Test agent        ┘
                    │  bulgular (JSON şema ile doğrulanmış)
                    ▼
               Judge agent ──► tekrarları ayıkla, önem sırasına koy ──► Markdown / JSON rapor
```

## Yol haritası

- [x] **Aşama 1:** Proje iskeleti, veri modelleri (`Finding`, `ReviewResult`, `FinalReport`), diff kaynağı
- [ ] **Aşama 2:** Uzman agent'lar (Claude Agent SDK)
- [ ] **Aşama 3:** Paralel orkestratör (timeout, hata izolasyonu, maliyet takibi)
- [ ] **Aşama 4:** Judge agent ve raporlama
- [ ] **Aşama 5:** CLI ve uçtan uca testler

## Kurulum

```bash
pip install -e ".[dev]"
pytest
```
