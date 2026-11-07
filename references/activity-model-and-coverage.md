# Activity model and source coverage

## Discovery scope

`data/activity-taxonomy.json` defines an extensible subject taxonomy, independent of audience and schedule. Explore every category for every geography before describing coverage as broad. Categories include outdoor recreation, sports participation and spectating, fitness, exhibits, history, science, nature, performance, literature, classes, camps, play, food, markets, festivals, games, community, volunteering, libraries, adaptive recreation and local exploration.

No fixed taxonomy can establish that every possible activity has been found. Add emerging categories rather than forcing them into “Other.” Age, disability access, price and adult/child/family audiences are separate dimensions; a subject is not an age restriction.

The generated graph carries category tags, supported activity formats and required leaves for each reviewed route. The category-by-region matrix covers all 22 categories × five regional bands. Each cell reports:

- `gap`: no reviewed route for this subject and region;
- `route_only`: a route exists, but current collection does not demonstrate a record for the category;
- `collecting`: a source actually returned records classified in this category.

This is a maintenance diagnostic, not proof of exhaustive recall. Inferred record classification remains labeled. Do not mark a whole subject as collected merely because a provider hosts it or its generic calendar returned other events. The graph separately audits routes and collected records for each activity format. Missing cells include concrete next-search queries.

## Required source leaves

Explore these beyond the provider's main event calendar:

| Activity | Leaves to inspect |
| --- | --- |
| Outdoor recreation | Trail maps, park/place directories, permitted uses, reservations, closures, water/weather conditions, seasonal access, equipment and guides |
| Sports participation | Adult/youth/adaptive programs, registration portal, season overview, roster/team rules, weekly fixtures, tryouts, equipment, signup deadline and rainout policy |
| Sports spectating | Team season schedules, individual fixtures, promotions, venues and ticket inventory |
| Exhibits | Current/upcoming exhibitions, full run, gallery hours, closed days, timed admission and separate special programs |
| Courses and camps | Term catalog/PDF, specific course or camp session, age eligibility, weekly attendance, prerequisites, registration opening, deadline and capacity |
| Recurring activities | Series parent, individual occurrences, cancellations, holiday exceptions and advance booking rules |
| Evergreen offerings | Official place/program description, opening hours and seasonal exceptions; never invent a one-day event merely to fit a calendar |

The initial expansion adds reviewed official routes for Weston Bend, JCPRD adult/youth sports, Lawrence recreation and youth soccer, Columbia programs and parks, Bentonville soccer/outdoor programs/schedules, volunteering and exhibition directories. Some require an adapter or deny automated access; those remain visible gaps. A route's presence is not a claim that its seasons are already in the inventory.

## Orthogonal fields

`schemas/activity.schema.json` defines the public activity contract. Its independent parts are:

- `categories`: one or more subject IDs, with `category_inferred`;
- `offering_id`: stable source-URL identity shared by dated occurrences;
- `id`: record/occurrence identity; different session dates remain separate;
- `parent_id`: optional explicit parent record, validated against orphan/cyclic links;
- `schedule`: format, participation/run start and end dates, explicit sessions, recurrence rule/time zone/exclusions, hours, closure exceptions and explanation;
- `registration`: status, opening, deadline and registration URL; never conflated with participation dates;
- `commitment`: drop-in/single-session/full-series/team-season attendance, duration and equipment;
- original source dates, status, prices, age guidance, evidence and observation timestamps.

Supported formats are one-off, multi-day, exhibit, sports season, course, camp, recurring program, evergreen, program catalog and an explicitly ambiguous date range. Categories and formats are separate: an outdoor activity can be a one-off guided walk, a six-week course, a camp or an evergreen trail.

### Schedule rules

An exhibit running October–February remains eligible for a December date-window search. That overlap does not establish that the gallery is open every day or that tickets are available. A sports season may run March–May while registration opens in November and closes in February. A course may require every weekly session. Never move the event start to the registration deadline or collapse the season into its first match.

Only use explicit source recurrence rules; keep `RRULE`, local time zone and excluded dates separately. Do not expand a run into daily occurrences or invent a weekly rule from prose like “regular classes.” Explicit sessions are retained as given. The current browser date filter checks the possible participation/run window, not guaranteed opening or session availability; visitors confirm hours and specific sessions on the show page/source. Unknown hours remain null.

Undated evergreen and program offerings use null event timestamps and are labeled as ongoing or dates-to-confirm. Date filters include these potential options by default, with an explicit checkbox to exclude them. They are not presented as confirmed events on a chosen day. Expired known runs leave the current inventory; unresolved future offerings remain as leads.

Classification from title/markup is marked inferred. Ambiguous multi-month source spans stay `date_range_unknown`; never assume a registration announcement is the season or that a long range is an exhibition. Existing records were migrated without changing source observation timestamps. Known source exhibition flags are preserved where available.

## Activity show page

`web/activity.html?id=<offering_id>` works directly on GitHub Pages, with no server routes or database. All cards link to it. The page shows:

- identity, subject, format, location and audience;
- published run/season window, explicit occurrences, recurrence, hours and exceptions;
- registration status/opening/deadline and source-listed price;
- participation commitment, duration and equipment;
- source links, source ownership, observation times, stale/conflict warnings;
- related occurrences grouped under a stable offering ID, without merging their distinct dates.

The official organizer page remains a separate outbound link. Unknown fields are explicit. Missing/expired IDs show a helpful unavailable state rather than another activity. Source content is inserted as text, not executable HTML.

## Maintenance and tests

Daily Actions regenerate the graph and coverage matrix, collect supported pages, validate the schedule schema and publish the static site. Add source adapters alongside fixtures for the actual public format. Tests cover undated trails, registration/season separation, exhibits overlapping a selected range, ambiguous spans, stable offering IDs, expiration, source coverage gaps and parent integrity. Browser checks cover internal card navigation, show-page facts, shared links, missing IDs and mobile width.

To improve source coverage, work from `gap` and `route_only` cells and the format audit rather than accumulating more copies of a well-covered museum's calendar. Review new program/trail/registration leaves before promoting them. The daily discovery retains same-provider leaves as well as external partners; a listing is not automatically trusted because it links from a reviewed root.
