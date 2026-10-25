# Smart Connect: pitch script

About 3 minutes spoken, plus a live call. Written 25 Oct 2026 against `main` = `7eb28d7`.
*Italic lines are stage directions.* Speaker labels are a suggestion: swap them as you like.

---

## 1. Hook (15 s) · Alex

> Hands up if you've ever put off a phone call: booking a table, a haircut, a GP appointment.
>
> *(pause)*
>
> Most of us have. Phone calls are slow, awkward, and only happen during opening hours. And loads of
> businesses still only take bookings by phone.
>
> So we built **Smart Connect**: you type what you want, and an AI agent **makes the phone call for you**.

## 2. Live demo (60–90 s) · Alex drives, Jamil plays the restaurant

*Before going on stage: Jamil's phone is the restaurant line (CALL_NUMBER), volume up, on speaker, not on silent.
Open the live site, go into an agent, and have this message already typed.*

> Let's book dinner. I'll type: **"Book a table for 2 at The Ivy Oxford tomorrow at 7pm."**

*Press Send. The agent shows "Thinking…", then the call panel appears and starts ringing.*

> Gemini has understood the request and decided it needs a phone call. Now it's ringing a real phone,
> Jamil's, who's playing the restaurant.

*Jamil answers on speaker and plays along: "The Ivy, how can I help?" Offer 7pm, ask for a name, say goodbye.*

> You can hear the voice agent: that's **ElevenLabs**. It introduces itself, asks for the table, gives
> my name for the booking, and hangs up politely when it's done.

*Call ends. The transcript and the Call result table appear.*

> As soon as the call ends, the transcript comes in, Gemini reads it and fills in this result table:
> confirmed, The Ivy Oxford, tomorrow, 19:00, table for 2.
>
> And it's not just on screen. *(hold up phone / switch tab)* It's in my **Google Calendar** with a reminder,
> and here's the **confirmation email** in my inbox, with the same details.

*If anything goes wrong mid-call: press **Hang up** and say "and if you change your mind, you can hang up
the call from the app at any time." Then move on to section 3.*

## 3. How we use ElevenLabs (40 s) · Jamil

> The voice is built on **ElevenLabs Agents**, connected to a real phone number through Twilio.
>
> - Every call is **briefed**: we pass the goal, the details and the acceptable alternatives into the agent
>   as dynamic variables, so each call is different. If 7pm is full and you said 7:30 is fine, it offers 7:30
>   itself; anything else, it politely turns down.
> - We use ElevenLabs' newest **expressive voice model**, so it sounds warm and natural rather than robotic.
> - The agent **ends the call itself** when the job is done, using ElevenLabs' end-call tool.
> - When the call finishes, ElevenLabs sends the full transcript to our server through a **signed webhook**,
>   which is what kicks off the rest of the app.
> - We tuned the turn-taking for real phone calls: for example, the opening line can't be cut off by the
>   person saying "Hello?" when they pick up.

## 4. How we use Gemini (40 s) · Alex

> If ElevenLabs is the voice, **Gemini is the brain**.
>
> - Gemini plans each task with **function calling**: place a call, add a calendar event, send an email.
>   It only gets the tools you've switched on for that agent, so a disabled tool literally can't be used.
> - A task **pauses** while the phone call happens, and **resumes** when the call ends.
> - Then Gemini turns a messy phone conversation into facts using **structured output**: strict JSON with
>   booked or not, the time, the name, any deposit, and *why* it failed: fully booked, no answer, voicemail.
> - Our code uses that to decide what happens next. Booked: calendar and email. Fully booked but they offered
>   a time you said was fine: it calls back once to take it. No answer: one retry. Voicemail: it doesn't
>   pester the business, it tells you. Never more than two calls per task.

## 5. Why two AIs? (15 s) · Alex or Jamil

> We deliberately split the jobs. Gemini is great at planning and using tools. ElevenLabs is great at
> fast, natural conversation. Keeping them apart also means the voice agent only ever knows the brief
> it was given: it can't decide to call someone else or spend your money.

## 6. Trust and safety (15 s) · Alex

> We built in guardrails from the start:
> - The AI is **honest that it's an AI** if anyone asks.
> - It **never invents results**: Gemini is only allowed to report what a tool actually confirmed, and only
>   confirmed bookings go in your calendar.
> - It can't dial random numbers: the server connects the call, not the model.
> - You stay in control: you can **hang up** any call from the app.

## 7. The stack (10 s) · anyone

> Gemini API for the brain, ElevenLabs and Twilio for the calls, Google Calendar and Resend for the
> follow-up, Postgres on **Tiger Data** for the call timeline, and it's all running live on a **Vultr** server.

## 8. Close (10 s) · Alex

> Smart Connect turns "I'll call them later" into "it's already done".
> Thanks, we'd love your questions.

---

## Q&A crib sheet

- **Is that a real phone call?** Yes: a real outbound call through Twilio to a real mobile. For the demo every
  call rings one teammate's phone (CALL_NUMBER), so we don't phone real businesses.
- **What if the restaurant asks something the agent doesn't know?** It only agrees to the goal or the
  alternatives you gave; anything else it says it'll check with you and call back.
- **What stops it booking the wrong thing?** The brief limits what it can accept, and Gemini checks the
  transcript afterwards; if it isn't clearly confirmed, it's reported as not booked.
- **Which models?** Gemini `gemini-3.1-flash-lite` (fast, about 2–4 s per step). ElevenLabs Agents with the
  `eleven_v4_turbo` expressive voice.
- **Could it do more than restaurants?** Yes: the call goal is general ("book a haircut Friday at 3",
  "ask if they have a table outside"). Restaurants are just the demo.
- **What about deposits?** Built but not live in this demo: the server side for approving a deposit during the
  call (approve/decline card, Stripe test mode) exists, but it isn't connected to the voice agent yet.
  Say "that's next" rather than demo it.

## Don't claim (not live as of this commit)

- Live transcript *during* the call: the panel shows ringing, answered, a timer and a voice wave live; the words
  appear when the call ends.
- Deposit approval during the call and Stripe charges (see above).
- Ignoring "yeah / okay" mid-sentence: the opening line is protected, but small "yeah"s can still cut the agent
  off. If it happens on stage, keep going.
