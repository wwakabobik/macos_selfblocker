# 🧱 Self-Blocker: MacOS tool to protect you from... yourself

![macOS](https://img.shields.io/badge/mac%20os-000000?style=for-the-badge&logo=macos&logoColor=F0F0F0)
![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)

## 📚 Table of Contents

- [❓ What is this?](#-what-is-this)
- [⚙️ Setup](#prerequisites)
- [🔧 Configure what to block and when](#configure-what-to-block-and-when)
- [🚀 Usage](#usage)

## ❓ What is this?

This tool is for people like me.

People who:
- have multiple jobs (because life’s a party and you're paying for the lights),
- haven’t been paid properly in months (but still feel responsible),
- work 12–14 hours because "well, someone’s gotta do it",
- keep delivering high-quality work for companies that treat them like doormats,
- know they should work less, but don’t trust themselves to actually do it.

This tool is for the times when your own brain is your worst boss.
When you can’t say "no" — so you build a system that says "no" for you. Loudly. Rigorously. By force.

## 🖥 Platform

This is a MacOS-only tool.

It uses:
- `launchd` to schedule blocking and unblocking actions (yes, the same system your OS uses to run maintenance stuff at 3am),
- `sudoers` config to run dangerous commands without password prompts (so it can execute even if you're AFK),
a bunch of custom Python scripts to block your:
- apps,
- directories,
- network access.

## 🔥 Why would anyone want this?

Because your life is on fire and you’re tired of holding the hose.
Because you’ve tried pomodoros, reminders, gentle nudges, and your therapist’s passive-aggressive questions.
And now it’s time to unplug the Ethernet cable with code.

You don’t need motivation.
You need a script that launches at 4pm and nukes your work environment.

## ☢️ What does it do?

You configure your "allowed work intervals" (like 11:00–15:00 Tue/Wed), and the system takes care of the rest:
Outside those intervals:
- 🪵 Blocks your project folders (chmod -r 000)
- 🧼 Kills work-related apps and prevents reopening them
- 🌐 Cuts off your internet access, if you’re being cheeky

Then unblocks everything the next day so you can do it all over again.
It’s like having a strict Eastern European dad, but in cronjob form.

# Prerequisites

Before using this tool, make sure to complete the following setup steps:

## 1. Make scripts executable

Ensure that the relevant Python scripts are marked as executable. Run the following command:

```bash
chmod +x work_control.py app_dropper.py dir_blocker.py net_blocker.py
```

You can also use `chmod +x *.py` in the script directory for convenience.
This allows the scripts to be run directly by launchd without explicitly invoking python.

## 2. Update sudoers to allow passwordless execution

scripts need root access (e.g. to block directories, applications, or networks), you should allow them to run via sudo without requiring a password. This ensures launchd can invoke them without manual intervention.

To do this:

- Open the sudoers file using the safe editor:
- 
```bash
sudo visudo
```

- Add the following lines at the end of the file, replacing `your_username` with your actual macOS username:

```bash
your_username ALL=(ALL) NOPASSWD: /path/to/dir_blocker.py
your_username ALL=(ALL) NOPASSWD: /path/to/app_dropper.py
your_username ALL=(ALL) NOPASSWD: /path/to/net_blocker.py
```

- Save and exit the editor.

- Tip: You can use the `whoami` command to confirm your current username:

⚠️ Important: Always use `visudo` when editing the `sudoers` file to avoid breaking your system configuration. A malformed file can disable sudo access completely.
Once this is done, your scripts will be able to run elevated tasks automatically as part of scheduled jobs.

# Configure what to block and when

## Directories to block

Create a text file named `work_paths.txt` in the same directory as the scripts. List each directory you want to block on a new line. For example:

```bash
/Users/your_username/Work/IFeelMyselfUnderpaid
/Users/your_username/Work/TheseGysTookMyMoney
/Users/your_username/Work/WhyAmIDoingThisAgain
```

That's it! The script will read this file to determine which directories to block during off-hours.
Yes, you will loose read-write-execute permissions to these directories during blocked hours, but they will be restored when unblocked.
That's first step - that will be harder to reach your work stuff, the better: all you configured envs, IDEs settings, git repos, and other useless in this life stuff.

## Applications to drop

Create a text file named `work_drop.txt` in the same directory as the scripts. List each application you want to drop on a new line, using the full path to the app. For example:

```bash
/Applications/Visual Studio Code.app
# apps to drop
Docker                      # GUI name (Docker Desktop)
bundle:com.docker.docker    # likely bundle id for Docker Desktop
proc:docker                 # match docker daemon processes if any
Slack
bundle:com.tinyspeck.slackmacgap
Zoom
bundle:us.zoom.xos
Mail
bundle:com.apple.mail
proc:Mail
```

You can use any of the following formats to specify applications, but I recommend using the GUI name.
Yeah, for sure, blocking directories not enough, because you still able to use cached stuff in your IDEs, terminals, browsers, etc.
So, this will close all your work-related apps. Yes, you may loose unsaved work... how pity.


## Network blocking

But you was not yourself, right? You may try to be sneaky and use web versions of your work apps, or access work resources via browser.
To get rid of Slack, your work sites, wikis, confluence, jira, email, etc. you must enable network blocking.

Create a text file named `work_domains.txt` in the same directory as the scripts. List each hostname you want to block on a new line. For example:

```bash
slack.com
zoom.us
mail.google.com
jira.yourcompany.com
confluence.yourcompany.com
api.patheticcompany.com
```

This will block network access to these domains during off-hours, resolving used IPs by digging them first.
These three horses of the apocalypse will make sure you can’t access your work stuff outside of allowed hours. Not bad, right?


## Work schedule

Probably you still want to work sometimes, right? So, you must configure your allowed work intervals.
To do this, create file named `workblock_schedule.json` in the same directory as the scripts.

Here is an example configuration:
```json
{
  "block": [
    {
      "Hour": 17,
      "Minute": 15,
      "Weekday": 4
    },
    {
      "Hour": 16,
      "Minute": 0,
      "Weekday": 5
    }
  ],
  "unblock": [
    {
      "Hour": 9,
      "Minute": 30,
      "Weekday": 4
    }
  ]
}
```

Or, way much better:
```json
{
  "intervals": [
    {
      "days": [2, 3],
      "start": { "Hour": 11, "Minute": 0 },
      "end": { "Hour": 15, "Minute": 0 }
    },
    {
      "days": [4],
      "start": { "Hour": 10, "Minute": 0 },
      "end": { "Hour": 18, "Minute": 0 }
    },
    {
      "days": [1, 5],
      "start": { "Hour": 12, "Minute": 0 },
      "end": { "Hour": 16, "Minute": 0 }
    }
  ]
}
```

This configuration specifies the times when blocking and unblocking actions should occur.

Simple blocking/unblocking times:
- `Hour`: The hour of the day (0-23) when the action should occur.
- `Minute`: The minute of the hour (0-59) when the action should occur.
- `Weekday`: The day of the week (1-7, where 1 is Monday and 7 is Sunday) when the action should occur.

Advanced schedule with intervals:
- `intervals`: List of allowed work intervals with specific days, start, and end times.
- `days`: List of weekdays (1-7) when the interval is active.
- `start`: The start time of the allowed work interval.
- `end`: The end time of the allowed work interval.

- You can specify multiple blocking and unblocking times as needed.

## Set up launchd jobs

To automate the blocking and unblocking actions, you need to create `launchd` job files.
To do so, just run script:

```bash
python plist_gen.py
```

Actually, you may pass input schedule file and output directory as arguments, e.g.:

```bash
python plist_gen.py --schedule path/to/your_schedule.json
```

This will generate and install the necessary `plist` files in your `~/Library/LaunchAgents` directory.

# Usage

All is set up now, so you can start using the tool.
If you try to unblock yourself during non-work hours, the script won't do it, moreover, all unblocked stuff will be blocked again soon.

## Can you override?

Sure, you can.
It's not strongest and robust, secure system in the world, but it will make your life harder to ruin your life with senseless work.

## Why not to block everything?
Actually, blocking everything is not a good idea, because you still want to use your computer for non-work stuff.
I wish I would block work stuff only, i.e. in GitHub, but I use it for personal stuff as well, for mine pet projects, so I need to cherry-pick what to block and what not. So, this tool gives you flexibility to choose what to block.

### 🤔 Why not use cron instead of launchd?

Because macOS is not Linux. `cron` on macOS is deprecated, not well-integrated with the system's app sessions, and doesn't support GUI session types like `Aqua`.  
`launchd` is the native and reliable way to schedule background jobs on macOS — it's what the OS itself uses.

## Logs

Logs are stored in `work_access_control.log` file in the same directory as the scripts, and `~/Library/Logs/workblocker` directory.

# One more thing

This isn't a productivity tool. It's a boundary-setting tool.

You're not lazy. You're tired.
You're not unmotivated. You're exploited.
You don't need to push harder — you need to stop pushing when it's time to rest.

This script is just one way to reclaim a little peace, one `chmod` at a time.

You don’t need more willpower. You need less opportunity to sabotage yourself.

If your job drains your soul, don't wait for permission to unplug.
Build tools that force you to walk away — even if your brain screams, “just five more minutes.”

This repo is my version of a fire escape. Use it, fork it, break the glass.

## Donations & contributions

If you like this project, you can support it by donating via [DonationAlerts](https://www.donationalerts.com/r/rocketsciencegeek), [Buy Me a Coffee](https://www.buymeacoffee.com/wwakabobik), or [ThanksDev](https://thanksdev.com/wwakabobik).

This is a personal project, so if you find any issues or have suggestions for improvement, please feel free to open an issue or submit a pull request on GitHub.
