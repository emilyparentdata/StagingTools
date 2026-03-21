# How to Get the Staging Tool on Your Mac

## Step 1: Open Terminal

- Press **Command + Space** on your keyboard (this opens Spotlight search)
- Type **Terminal**
- Click on **Terminal** when it appears (it has a black screen icon)
- A window will open with a blinking cursor — this is where you'll type commands

## Step 2: Go to Your Desktop

In the Terminal window, type this exactly and press **Enter**:

```
cd ~/Desktop
```

This tells your computer "go to my Desktop folder." You won't see anything happen — that's normal.

## Step 3: Install Git (if you don't have it)

Type this and press **Enter**:

```
git --version
```

**If you see a version number** (like `git version 2.39.0`), skip to Step 4.

**If a pop-up appears** asking you to install "command line developer tools," click **Install** and wait for it to finish. This can take a few minutes.

## Step 4: Download the Project

Type this and press **Enter**:

```
git clone https://github.com/emilyparentdata/StagingTools.git
```

You'll see some text scroll by. When it's done and you see the blinking cursor again, the project has been downloaded. If you look at your Desktop, you should see a new folder called **StagingTools**.

## Step 5: Go Into the Project Folder

Type this and press **Enter**:

```
cd StagingTools/staging-tool
```

## Step 6: Set Up Python

Type each of these lines one at a time, pressing **Enter** after each one. Wait for each to finish before typing the next:

```
python3 -m venv venv
```

```
. venv/bin/activate
```

After the second command, you should see `(venv)` appear at the beginning of your line. That means it worked.

```
pip install -r requirements.txt
```

This one will take a minute — you'll see a lot of text scrolling. Wait until you see the blinking cursor again.

## Step 7: Set Up Your Settings File

```
cp .env.example .env
```

Now open the `.env` file to add your API key. Type:

```
open -e .env
```

This opens the file in TextEdit. You'll see a line that says `ANTHROPIC_API_KEY=`. Paste your API key right after the `=` sign (no spaces). Save the file (**Command + S**) and close TextEdit.

## Step 8: Run the Tool

```
python staging.py
```

You should see something like `Running on http://127.0.0.1:5000`. Open your web browser (Safari, Chrome, etc.) and go to:

**http://localhost:5000**

The staging tool should appear!

---

## Every Time After the First Time

You only need to do Steps 1-7 once. After that, whenever you want to run the tool:

1. Open **Terminal** (Command + Space, type Terminal)
2. Type these commands one at a time:

```
cd ~/Desktop/StagingTools
```

This takes you to the project folder.

```
git pull
```

This downloads the latest version of the tool. You'll either see a list of updated files, or it will say `Already up to date.` — both are fine.

```
cd staging-tool
```

```
. venv/bin/activate
```

You should see `(venv)` appear at the beginning of your line.

```
pip install -r requirements.txt
```

This makes sure any new dependencies are installed. Usually it will say `Requirement already satisfied` — that's fine. Only takes a second.

```
python staging.py
```

3. Open **http://localhost:5000** in your browser

---

## If Something Goes Wrong

- **"command not found"** — Make sure you typed the command exactly as shown, including spaces and capital letters
- **"No such file or directory"** — You might be in the wrong folder. Type `cd ~/Desktop/StagingTools/staging-tool` and try again
- **The tool won't start** — Make sure you see `(venv)` at the beginning of your Terminal line. If not, type `. venv/bin/activate` first
