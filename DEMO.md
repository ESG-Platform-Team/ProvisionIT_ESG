# Showcase script

About eight minutes. Runs fully offline against the fixture company, so bad
wifi can't break it.

## Before you start

```
cd ~/Downloads/ProvisionIT-ESG
./demo.sh --reset
```

The browser opens at http://localhost:8001. The first time, click **Create an account**
(name, email, a password of 10+ characters). After that, sign in. Keep that terminal open; Ctrl-C
stops everything.

Want the language model instead of keyword matching? Put your Gemini key in
`backend/.env` and run `./demo.sh --reset --live`. Keyword mode is the safer
demo because it does not depend on the API.

## 1. One search, three pillars (1 min)

1. Type `TST` and leave all three pillar chips on: Governance, Environmental,
   Social.
2. Press Enter. The retrieval screen shows each document as it is fetched:
   the governance statement, climate statement, sustainability report, modern
   slavery statement, privacy policy.
3. Point out the one that failed: the reconciliation action plan link is
   broken on purpose. It shows as not found and is not hidden.

Say: "One crawl feeds all three pillars. Nothing is fetched twice."

## 2. The disclaimer Mick asked for (1 min)

1. Open the assessment. The amber banner at the top says the assessment was
   formed by software, names the reader, and says no analyst has reviewed it.
2. Open any finding. Each one says it was interpreted by a machine.

Say: "The machine makes the interpretation, and we say so on every screen and
in every export."

## 3. Environmental and Social (2 min)

1. Switch the tabs in the header: Governance, Environmental, Social.
2. Environmental: climate statement findings (grade A source), emissions,
   targets, the Scope 3 criterion.
3. Social: modern slavery, workforce, privacy and cyber security. Security
   sits here as S5.
4. Point at the draft note: the Environmental and Social criteria are v0.1
   drafts until Chen Yu signs them off.

Say: "Same engine, same five states, same two scores. The pillars are just
different question sets."

## 4. PDF report by email (1.5 min)

1. Click **Download PDF report**. Show the cover (every pillar on one page,
   with the machine interpretation box), then a pillar page with excerpts and
   page numbers, then the source log.
2. Click **Email report**, enter an address, send.
3. The screen says it was saved, not sent, because SMTP is not configured.
   That is deliberate: a demo can never email a real person by accident.
4. Optional: show the saved email with the PDF attached. In a second terminal:
   `open backend/data/mail/*report*.eml`

Say: "Add SMTP settings, or Amazon SES on AWS, and the same button delivers."

## 5. Asking the company for what is missing (2.5 min)

1. Click **Request missing disclosures**. It lists every criterion public
   sources did not answer. Enter your name and send.
2. Open the saved request email (`open backend/data/mail/*disclosure-request*.eml`):
   the list of items, the due date, the secure link, how a response is used,
   what happens with no reply, the opt-out.
3. Click **Open the company's response page**. This is what the company sees.
   Upload any PDF, for example
   `backend/fixture-site/docs/modern-slavery-statement-2026.pdf`, and send.
4. Go to **Requests**. The status is Responded. Click **View documents** to see
   what they sent, who sent it and what was asked for; **Open** shows the file in
   a new tab. Then click **Re-assess**. The new run includes the company's
   document, marked *provided on request* and graded C, below anything published.

Private company version: in **Requests**, type a company name in the composer,
choose **Add it**, give its website, click **Find published contacts** to pull
the addresses it publishes, tick the documents you want and watch the email
preview update. Use your own email as the contact for the demo.

Then show the other outcome:

5. Run TST again, send a new request, and in **Requests** click **Close**
   (standing in for the due date passing). Re-assess.
6. Open a criterion that was asked for. The note reads "Requested on ...,
   closed without a response ..., so it is reported as insufficient
   information" and the rating has not changed.

Say: "We never scrape anything private. We ask. If they answer, it counts,
marked as provided on request. If they don't, it is insufficient information,
never a zero."

## If something goes wrong

| Problem | Fix |
|---|---|
| "Port 8001 is in use" | `kill $(lsof -ti tcp:8001)` (same for 8080, 8123) |
| "still open for this company" when requesting | Close the open request in Requests, or restart with `./demo.sh --reset` |
| Old page cached | Hard refresh with Cmd+Shift+R |
| Blank assessment | Check the terminal for a Python error and restart `./demo.sh` |

## Questions to expect

- **Is the score from the AI?** No. The model only reads and quotes. Plain code
  decides the score, and the same findings always give the same score.
- **Can a company game it by sending documents?** They count, but they are
  labelled as provided on request and graded below published documents.
- **Is emailing companies allowed?** One request per company at a time, it
  says who is asking and why, and it has an opt-out we honour. Chris to confirm
  against the Spam Act before we send any real ones.
