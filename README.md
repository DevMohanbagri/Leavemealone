# LeaveMeAlone

A local desk for finding your personal data on people-search sites and data brokers, filing the official opt-outs, and watching in case it comes back.

It does not hack broker sites, skip human checks, or promise that every copy on earth disappears. You send every request yourself. The dossier stays in a database on this machine.

## What it does

**Where.** Scans public people-search pages, a web index, and known breach lists for the name, city, and email you provide. If a site puts up a captcha or a bot wall, the scan stops and gives you the link. Phone numbers are not put in search URLs unless you turn that on.

**Pull.** Walks official opt-out pages, writes a deletion letter under the privacy law of your state of residence (CCPA/CPRA, the Delete Act, TDPSA, GDPR, and others), and batches privacy-inbox addresses so you can BCC them from your own mail. California residents are pointed at [DROP](https://privacy.ca.gov/drop/) first. Deadlines are tracked. Missed deadlines get a follow-up and a complaint draft.

**Watch.** Rechecks pages that had you, pages that blocked the last look, and your email. A cleared listing that returns becomes an alert. The watch runs only while this app is running.

Public records held by a court or a county recorder are not something a broker opt-out can erase. A published data breach cannot be undone either — change the password.

## Run it

```bash
pip install -r requirements.txt
python run.py
```

Open http://127.0.0.1:8787

The sample dossier (Avery Quinn) is fictional, so you can learn the desk without typing a real name. Live scans and the watch refuse to run against the sample.

## Privacy

- The dossier, removal log, and optional Have I Been Pwned key are stored in `data/leavemealone.db`.
- A scan you start sends your name (and city, if you added one) to the public pages it checks, and your email to a breach index. Date of birth is never put in a search URL, and it is left out of letters unless you opt in.
- LeaveMeAlone does not email brokers for you. Drafts and mailto text are yours to send.
- This is not legal advice. The letters are consumer requests you should read before sending.

## Directory

Broker contact data and opt-out notes are adapted from the [DataPurge](https://github.com/puurpl/datapurge) registry (MIT). See `NOTICE.md`. Pages move. If a link is dead, use the privacy link in the broker's footer.

Refresh the catalog from a local DataPurge checkout:

```bash
python scripts/build_catalog.py /path/to/datapurge/brokers
```

## Tests

```bash
python -m unittest tests.test_core
```
