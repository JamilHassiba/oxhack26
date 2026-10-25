# Smart Connect: booth script

For a booth, not a stage: people walk up, you have **30 seconds** to hook them and **2–3 minutes** if they stay.
Built around the prizes we entered: **ElevenLabs, Gemini API, Tiger Data, Vultr** (and the DEV Writing
Challenge if we publish a post). Written 25 Oct 2026 against `main` = `1172e2f`.

---

## Before anyone arrives (checklist)

- Laptop: the live site open in an agent's chat (https://192-248-148-174.sslip.io), the slide deck open on the cover slide,
  and a second tab with **one finished booking** (transcript + Call result table) as a backup.
- The restaurant phone (`CALL_NUMBER`, Jamil's) charged, **on speaker, volume up, not on silent**.
  Calls come from a US number: answer anyway.
- Google Calendar and the inbox (hydrachops1234@gmail.com) open in tabs, to show the booking landed.
- Delete or rename joke test agents on the live site.
- Who does what: **one person talks** to the visitor, **one person plays the restaurant** on the phone.

---

## 1. The 30-second hook (say this to everyone)

> Hi! This is **Smart Connect**. You know those phone calls you keep putting off, booking a table, a haircut?
> You just type what you want, and an AI agent **makes the real phone call for you**, books it, and puts it in
> your calendar. Want to see it ring a phone right now?

*If they say yes: go to section 2. If they're a sponsor judge: lead with their section in 3.*

## 2. The live demo (about 90 seconds)

1. Type: **“Book a table for 2 at The Ivy Oxford tomorrow at 7pm.”** and press Send.
   > Gemini reads that, works out it needs a phone call, and writes a brief for the voice agent.
2. The call panel rings. The phone on the table rings.
   > That’s a real call over Twilio. For the demo, every call rings our teammate’s phone, so we never call a real business.
3. The teammate answers on speaker and plays the restaurant (offer 7pm, ask for a name, say goodbye).
   > This voice is **ElevenLabs**. It knows the time you asked for and the alternatives you allowed, gives your name for the booking, and hangs up by itself.
4. The call ends: transcript, summary and the **Call result** table appear.
   > Gemini reads the transcript and turns it into facts: confirmed, The Ivy Oxford, tomorrow, 19:00, table for 2.
5. Switch tabs: **Google Calendar** event with a reminder, and the **confirmation email** with the same table.
   > And it’s in my calendar and my inbox. That’s one sentence in, finished booking out.

**If the call fails or nobody answers:** say “and if nobody picks up, it tells you, and it can try once more”,
then show the backup tab with a finished booking. Press **Hang up** if a call goes wrong: “you can stop any
call from the app.”

---

## 3. Prize by prize

Use the matching section when a sponsor judge comes by, or when someone asks “how does it work?”.
Each has a **20-second pitch**, **what to show**, and **answers to likely questions**.

### 🎙️ Best Use of ElevenLabs

**Pitch:**
> ElevenLabs is the part that actually talks. We use **ElevenLabs Agents** connected to a real phone line through
> their **Twilio integration**. Every call is **briefed**: Gemini’s plan goes in as **dynamic variables**: the goal,
> the details, and the alternatives you allowed, so every call is different. It uses the newest **expressive
> voice model**, ends the call itself with the **end-call tool**, and when the call finishes ElevenLabs sends the
> transcript to our server through a **signed webhook**, which kicks off everything else.

**Show:** a live call on speaker; then the transcript in the chat.

**Extra points to mention:**
- We tuned turn-taking for phone calls: the opening line can’t be cut off when the person says “Hello?” as they pick up.
- The **Hang up** button: ElevenLabs gives us the Twilio call ID when a call starts, so the app can end a live call.
- It’s honest: if asked, it says it’s an AI assistant.

**Likely questions:**
- *Is the voice real-time?* Yes, it’s a live two-way conversation, not a recording.
- *How does it know what to say?* The brief from Gemini plus a short system prompt: only accept your time or your alternatives; anything else, it says it’ll check with you.
- *Why not let Gemini talk directly?* ElevenLabs is built for fast, natural voice; we keep the planner and the voice separate (see “Why two AIs”).

### 🧠 Best Use of Gemini API

**Pitch:**
> Gemini is the brain. It plans each task with **function calling**: place a call, add a calendar event, send an
> email. An agent only gets the tools you switched on, so a disabled tool can’t be used at all. The task **pauses**
> while the call happens and **resumes** when it ends. Then Gemini uses **structured output** to turn a messy phone
> call into strict JSON: booked or not, time, name, deposit, and *why* it failed. Our code uses that to decide the
> next step.

**Show:** send a request and point at “Thinking…”, then the Call result table after the call.

**Extra points to mention:**
- **Smart follow-ups:** fully booked but they offered a time you allowed → it calls back once to take it. No answer → one retry. Voicemail → it doesn’t pester the business, it tells you. Never more than two calls.
- **Never invents results:** it only reports what a tool confirmed, and only confirmed bookings go in the calendar.
- **Times:** Gemini gives UK clock time and our code attaches the timezone (it got today’s clock change wrong in testing, so we fixed that in code).
- Model: `gemini-3.1-flash-lite`, about 2–4 seconds per step.

**Likely questions:**
- *What if the request is vague?* It says exactly what’s missing (time, place) instead of guessing.
- *Can it do more than restaurants?* Yes, the call goal is general: haircuts, appointments, asking a question.

### 🐯 Best Use of Tiger Data

**Pitch:**
> Our database is **Tiger Data**: Postgres with TimescaleDB. A phone call is naturally a **time series**: dialling,
> ringing, answered, each transcript line, ended. So every call is stored as events in a **`call_events`
> hypertable**, and the call panel in the chat is **streamed live from that table** with server-sent events.
> Ringing and answered come in live from Twilio and are written there as they happen.

**Show:** the call panel moving from Calling → Ringing → Answered with the timer; then the finished timeline.

**Extra points to mention:**
- All app data lives there too: agents, tasks, calls, payments.
- We also built a **continuous aggregate** of hourly call stats on the hypertable (refreshed automatically). It isn’t
  shown in the current UI (we simplified the app to two pages), so mention it as built, not as a screen.

**Likely questions:**
- *Why a hypertable and not a normal table?* Call events are append-only, time-ordered and grow fast; TimescaleDB partitions them by time and makes time queries and aggregates cheap.

### ☁️ Best Use of Vultr

**Pitch:**
> Everything you’re seeing runs **live on a Vultr VM** in London: the FastAPI backend under systemd, behind
> **Caddy** for automatic HTTPS, which also serves the built website. ElevenLabs needs a public HTTPS address
> for its webhook, and Vultr gives us that.

**Show:** the live URL in the address bar (not localhost).

**Extra points to mention:**
- Our **deploy script** builds each version into its own release folder, checks the Caddy config, switches over
  atomically, and **rolls back automatically** if the health check fails. We deployed dozens of times today with no downtime.
- Live updates of the call panel go through Caddy unbuffered, so events arrive instantly.

### ✍️ DEV Writing Challenge (only if the post is published)

> We wrote up how we built it on DEV: [link]. *(Not published yet: publish before submitting, or leave this out.)*

---

## 4. Why two AIs? (when someone asks)

> We split the jobs on purpose. Gemini is great at planning and tools; ElevenLabs is great at natural conversation.
> It also keeps things safe: the voice agent only knows the brief it was given, so it can’t decide to call someone
> else or spend your money.

## 5. General questions

- **Is that a real call?** Yes, a real outbound call through Twilio. For the demo it always rings our teammate’s phone (`CALL_NUMBER`).
- **What stops it booking the wrong thing?** The brief limits what it can accept, and Gemini checks the transcript afterwards; if it isn’t clearly confirmed, it’s reported as not booked.
- **What about deposits?** The server side is built (approve/decline card, Stripe test mode) but not connected to the voice agent yet. Say “that’s next”.
- **What would you build next?** Deposits during the call, calling in other languages, and calling several places at once to find the best time.

## Don’t claim (not live as of this commit)

- Approving a **deposit during the call**, or Stripe charges: not connected (the voice agent only has the end-call tool, and no Stripe key is set).
- Words appearing **during** the call: the panel shows ringing, answered, timer and voice wave live; the transcript appears when the call ends.
- A **stats/analytics screen**: the Tiger Data aggregate exists but isn’t shown.
- Ignoring small “yeah”s: the AI can still get cut off mid-sentence. If it happens, carry on.
