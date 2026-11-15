# PR Reviewer: Multi-Agent Code Review

Bir pull request diff'ini paralel çalışan uzman AI agent'larına inceleten, sonuçları bir **Judge** agent'ında birleştiren orkestrasyon projesi.

- **Framework:** [Claude Agent SDK](https://code.claude.com/docs/en/agent-sdk) (`claude-agent-sdk`)
- **Orkestrasyon:** Python `asyncio`

## Mimari

```
diff ──► Orchestrator (asyncio)
           ├─► Security agent    ┐
           ├─► Performance agent │  paralel (asyncio.gather + Semaphore)
           ├─► Readability agent │  her biri Read/Grep/Glob ile repoyu okuyabilir
           └─► Test agent        ┘
                    │  bulgular (JSON şema ile doğrulanmış)
                    ▼
               Judge agent ──► tekrarları ayıkla, önem sırasına koy ──► Markdown / JSON rapor
```

| Desen | Nerede |
|---|---|
| **Fan-out / fan-in** | `orchestrator.py` tüm uzmanları paralel çalıştırır, `agents/judge.py` sonuçları birleştirir |
| **Uzman agent'lar** | `agents/specialists.py`: her biri tek bir konuya odaklı prompt ve kontrol listesi |
| **Yapılandırılmış çıktı** | Agent'lar JSON şemaya uygun cevap verir (`output_format`), serbest metin ayrıştırılmaz |
| **Hata izolasyonu** | Bir agent çökse, zaman aşımına uğrasa ya da hata dönse bile diğerleri devam eder |
| **Halüsinasyon koruması** | Judge yalnızca uzmanların bulgularına ID ile atıf yaparak bulgu üretebilir; atıfsız bulgu atılır |
| **Graceful degradation** | Judge çalışmazsa bulgular deterministik olarak birleştirilir |
| **En az yetki** | Agent'lar yalnızca Read/Grep/Glob kullanır; dosya yazamaz, komut çalıştıramaz |
| **Maliyet kontrolü** | Her agent çalıştırmasına USD bütçe sınırı; raporda agent başına maliyet |
| **Test edilebilirlik** | Tüm LLM çağrıları `AgentRunner` arayüzünden geçer; testler sahte runner ile API'siz çalışır |

## Kurulum

```bash
pip install -e ".[dev]"
export ANTHROPIC_API_KEY=sk-ant-...   # Claude Agent SDK için
```

## Kullanım

```bash
# Mevcut branch'i main'e göre incele
pr-review --base main

# Örnek diff ile dene (SQL injection, shell injection ve N+1 sorgu içerir)
pr-review --diff-file examples/vulnerable.diff

# Sadece bazı uzmanlar, JSON çıktı, dosyaya yaz
pr-review --base main --reviewers security,testing --format json -o review.json

# stdin'den
git diff main | pr-review --stdin

# CI kapısı: high veya critical bulgu varsa exit code 1
pr-review --base origin/main --fail-on high
```

| Seçenek | Varsayılan | Açıklama |
|---|---|---|
| `--model` | `claude-opus-5-5` | Tüm agent'ların modeli |
| `--max-budget` | `1.0` | Agent çalıştırması başına USD sınırı |
| `--timeout` | `600` | Uzman başına saniye |
| `--concurrency` | `4` | Aynı anda çalışan uzman sayısı |
| `--fail-on` | `never` | Bu ciddiyette bulgu varsa exit 1 |

Exit kodları: `0` sorun yok · `1` `--fail-on` eşiği aşıldı · `2` hata (geçersiz girdi ya da tüm uzmanlar başarısız).

## Proje yapısı

```
pr_reviewer/
  models.py          Finding / ReviewResult / FinalReport + JSON şemaları
  diff_source.py     git, dosya veya stdin'den diff
  runner.py          AgentRunner arayüzü + ClaudeAgentRunner (Claude Agent SDK query())
  agents/
    specialists.py   4 uzman tanımı
    reviewer.py      bir uzmanı çalıştırma
    judge.py         birleştirme, ayıklama, karar
  orchestrator.py    paralel fan-out, timeout, hata izolasyonu
  pipeline.py        uçtan uca review()
  report.py          Markdown / JSON
  cli.py             pr-review komutu
tests/               37 test, sahte runner ile, API çağrısı yok
```

## Yeni uzman eklemek

`pr_reviewer/agents/specialists.py` içindeki `SPECIALISTS` listesine bir `Specialist(name=..., focus=..., checklist=(...))` ekle. Orkestratör ve CLI onu otomatik olarak kullanır.

## Yol haritası

- [x] **Aşama 1:** Proje iskeleti, veri modelleri, diff kaynağı
- [x] **Aşama 2:** Uzman agent'lar (Claude Agent SDK)
- [x] **Aşama 3:** Paralel orkestratör (timeout, hata izolasyonu, maliyet takibi)
- [x] **Aşama 4:** Judge agent ve raporlama
- [x] **Aşama 5:** CLI ve uçtan uca testler
- [ ] GitHub Action: her PR'da otomatik çalıştır ve sonucu yorum olarak yaz
- [ ] Büyük diff'leri dosya gruplarına bölüp paralel inceleme
