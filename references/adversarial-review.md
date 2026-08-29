# Adversarial review

Challenge every likely selection. The goal is to find the reason a seemingly attractive recommendation would disappoint the user.

## Required checks

- **identity:** Are similarly named events or recurring editions being confused?
- **date and time:** Is the date for the correct year and occurrence? Is the time local and is an end time or arrival window material?
- **location:** Is the venue correct, including city and any last-minute relocation?
- **operating state:** Has the organizer posted a cancellation, postponement, closure, or schedule change?
- **availability:** Are tickets, seats, timed entries, or registrations actually open? Is a waitlist being mistaken for availability?
- **deadline:** For signup-horizon results, is the registration or on-sale deadline current and distinct from the event date?
- **price:** Does the quoted cost include required admission, registration, materials, parking, or likely fees? Label unknown fees.
- **audience and restrictions:** Check age limits, membership, skill prerequisites, waivers, accessibility, and whether the activity is public.
- **fit:** Does the candidate genuinely match the party and preferences, or is it merely prominent or unusual?
- **travel:** Is the regional option worth the real time and coordination compared with KC alternatives?
- **weather and season:** Could conditions make the activity impractical, and is there a credible fallback?
- **provenance:** Was the source graph actually swept first? If discovered via broader search, was first-party verification added without erasing its discovery label?
- **conflicts:** Do first-party and secondary sources disagree on any material fact?
- **promotion bias:** Did sponsorship, affiliate placement, or repeated publicity influence inclusion without improving fit?

## Outcomes

- `pass`: Material details are verified and no important objection remains.
- `hold`: A resolvable uncertainty remains. Recheck or present only as a clearly labeled backup if the user can resolve it safely.
- `fail`: A hard gate, contradiction, or likely disappointment remains. Do not recommend it.

All final selections must be `pass`. If live conditions can change after the check, include the observation time and a concise recheck note.
