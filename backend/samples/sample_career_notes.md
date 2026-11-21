# Faster deployments for the billing service

Situation: Our billing service took 40 minutes to deploy and the team froze releases every weekend because deployments were risky.

Task: I was asked to cut deployment time and remove the weekend release freeze without hurting reliability.

Action: I containerized the service with Docker, added a staged rollout with automatic rollback, and wrote smoke tests that ran after each deploy. I paired with two teammates to migrate the pipeline step by step and documented every change in the team wiki.

Result: Deployments dropped from 40 minutes to 12 minutes. We shipped twice a day with no failed releases for six months, and the weekend freeze was removed.

---

# Mentoring two interns

Situation: Two summer interns joined my team with little experience in backend development, and my manager wanted them to ship something real.

Task: I became their mentor and was responsible for helping them deliver a useful feature in ten weeks.

Action: I split the project into small weekly goals, ran code reviews twice a week, and taught them testing and debugging with real examples from our codebase. When one intern struggled with confidence, I gave her ownership of a small feature and checked in daily.

Result: Both interns shipped a reporting feature used by the support team. One received a full-time offer, and my manager asked me to lead the next mentoring program.

---

# Resolving the checkout outage

Situation: On a Friday evening our checkout page started failing and customers could not pay. The on-call engineer was unreachable.

Task: I volunteered to lead the incident response because I knew the payment code best.

Action: I traced the errors to an expired certificate used by a payment provider, rolled out a temporary fix, and coordinated updates to customer support every thirty minutes. The next week I wrote a postmortem and added automated certificate expiry alerts.

Result: Checkout was restored in 55 minutes. The expiry alerts have since caught two certificates before they expired, preventing repeat outages.

---

# Cutting API latency with caching

Situation: The product search API was slow during peak hours, with a median response time of 900 milliseconds, and customers complained.

Task: I owned the investigation and had to reduce latency before the holiday sales.

Action: I profiled the service, found that the same expensive database queries ran repeatedly, and added a Redis cache with sensible expiry times. I also rewrote two slow SQL queries and added an index.

Result: Median latency fell from 900 to 140 milliseconds and database load dropped by half during the holiday peak.
