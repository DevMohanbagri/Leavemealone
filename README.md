# LeaveMeAlone

A private desk that runs on your computer. It looks for public copies of your name on people-search sites, walks you through the official opt-outs, writes the deletion letters, and checks back if a listing returns.

You send every request yourself. The app does not email brokers for you, does not skip captchas, and does not break into websites.

## Is it safe to run on your computer?

Yes, if you run it the way this guide says.

What it does **not** do:

- It does not install a background service. It runs only while the terminal window is open. Close that window, or press Ctrl+C, and it stops.
- It does not create an account, and it does not send your dossier to us. There is no company server behind this app.
- It does not read your email, your photos, or your other files. Your details live in one file: `data/leavemealone.db`, next to the code.
- It does not message data brokers. Letters and draft emails are copied to your own mail app. You press send.
- It does not bypass human checks on websites. If a site blocks an automated look, you get the link and open it yourself.

What you should know before you type a real name:

- The page has no password. That is fine, because it only listens on your own computer (`127.0.0.1`). Do not change that to share it on a cafe Wi-Fi or a public server.
- A scan you start will send the name and city you typed to the public pages you asked it to check, and your email to a breach-list service. That is the lookup. Nothing is sent until you click Scan.
- Date of birth stays out of search links, and out of letters, unless you turn that on.
- Do not run it on a computer other people can log into if you do not trust them. They could open the same page and read the dossier.
- Get the code from [this repository](https://github.com/DevMohanbagri/Leavemealone), not from a random re-upload.
- The letters are consumer requests, not legal advice. Read them before you send them. A broker can ignore you. A court record or a county deed cannot be erased by an opt-out.

Until the pull request is merged, the working code is on the branch `arena/01a0d4ff-leavemealone`, not on `main`. `main` is only the license file. The steps below use the right branch.

## What you need

- A computer running Windows, macOS, or Linux
- Python 3.10 or newer. 3.11 or 3.12 is a good choice.
- An internet connection, only if you want live scans. The sample dossier works without one.

Check Python by opening a terminal and running:

```bash
python3 --version
```

On Windows, if that fails, try:

```bash
py -3 --version
```

If you do not have Python, install it from [python.org/downloads](https://www.python.org/downloads/). On Windows, tick **Add python.exe to PATH** during setup.

## Easy start

### 1. Get the code

If you have Git:

```bash
git clone --branch arena/01a0d4ff-leavemealone https://github.com/DevMohanbagri/Leavemealone.git
cd Leavemealone
```

If you do not have Git, download this zip and unzip it, then open a terminal in that folder:

https://github.com/DevMohanbagri/Leavemealone/archive/refs/heads/arena/01a0d4ff-leavemealone.zip

After the pull request is merged into `main`, you can clone the repository without `--branch`.

### 2. Make a private Python folder and install

This keeps the install off the rest of your system.

**macOS or Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

**Windows (Command Prompt)**

```bat
py -3 -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
```

**Windows (PowerShell)**

```powershell
py -3 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

If PowerShell refuses to run the activate script, use Command Prompt for this step. You only need the three packages in `requirements.txt`: FastAPI, Uvicorn, and HTTPX.

### 3. Start it

```bash
python run.py
```

Leave that window open. When it says the server is running, open this address in your browser:

http://127.0.0.1:8787

If that port is already taken:

```bash
# macOS or Linux
LEAVEMEALONE_PORT=8790 python run.py

# Windows Command Prompt
set LEAVEMEALONE_PORT=8790
python run.py
```

Then open http://127.0.0.1:8790

### 4. Use it

1. Click **Walk the sample** first. Avery Quinn is not a real person. Use that to learn the desk.
2. When you are ready, click **Open a dossier** and enter your own name. Country, state, and city take any place: type to search, or type a city that is not listed. Confirm it is your information, or that you are allowed to act for this person.
3. **Scan** looks for public listings. In some networks the sites refuse an automated look. The letters still work. Open the search link yourself and record what you see.
4. **Pull** is the removal queue: official opt-out pages, a letter under your state privacy law, and email batches you send from your own mailbox. California residents should file [DROP](https://privacy.ca.gov/drop/) first.
5. **Watch** rechecks while the app is running. Turn the computer off, and the watch pauses. Start the app again and it can check on the schedule you set.

### 5. Stop it

Click the terminal window and press **Ctrl+C**. On macOS that is the same keys. The dossier file stays on disk, so the next start remembers your progress.

To start it again later, open a terminal in the same folder, activate `.venv` the same way as step 2, and run `python run.py`.

## Where your data sits

| What | Where |
| --- | --- |
| Your dossier, sightings, and removal log | `data/leavemealone.db` on this computer |
| Optional Have I Been Pwned key | same database, only if you paste one in |
| Broker directory | `data/brokers.json`, already in the download |

Delete `data/leavemealone.db` to erase the local dossier. That does not tell any broker to delete you. Use **Export dossier** in the app first if you want a backup.

Do not post that database file, or an export, in a public place. It contains the name, email, and address you typed.

## If something goes wrong

- **`python` is not recognized.** Use `python3` on Mac or Linux, or `py -3` on Windows. Install Python and, on Windows, enable Add to PATH.
- **`No module named uvicorn`.** The virtual environment is not active, or install did not finish. Run the activate command again, then `python -m pip install -r requirements.txt`.
- **The browser cannot connect.** The terminal must still be running. Use `http://127.0.0.1:8787`, not a public website address.
- **Scan says the sites did not answer.** Your network, or the site, blocked the automated check. Open the link from the case desk and record the page yourself. This is normal on some Wi-Fi networks.
- **The opt-out page says you have been blocked.** That is the site's own security wall, often on people-search sites such as TruePeopleSearch. Do not try to get around it. In the desk, use **Email the letter** and send it from your own mailbox. If no mail app opens, the letter stays on the page so you can paste it into Gmail or Outlook. For TruePeopleSearch the published address is support@truepeoplesearch.com. You can also call 888-838-4803 or mail the same letter to PO Box 7775 PMB 29296, San Francisco, CA 94120-7775.
- **PowerShell blocks activate.** Use Command Prompt, or run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` once in that window, then activate again.

## Tests

Optional. From the project folder, with the virtual environment active:

```bash
python -m unittest tests.test_core
```

## Directory notes

Broker contact data is adapted from the [DataPurge](https://github.com/puurpl/datapurge) registry (MIT). See `NOTICE.md`. Opt-out pages move. If a link is dead, use the privacy link in the site's footer.

To rebuild the catalog from a local DataPurge checkout:

```bash
python scripts/build_catalog.py /path/to/datapurge/brokers
```
