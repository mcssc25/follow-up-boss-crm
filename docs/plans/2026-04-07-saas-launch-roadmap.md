# SaaS Launch Roadmap for Real Estate CRM

**Date:** 2026-04-07  
**Status:** Draft  
**Goal:** Turn the current CRM into a packaged, reliable, sellable SaaS product for real estate agents, starting with a beta and progressing to paid launch.

## Product Direction

### Core v1 Offer

This is the launch package the product should be built around:

- CRM / contacts
- Lead capture landing pages
- Pipeline management
- Tasks and reminders
- Email automation and drip campaigns
- Gmail connection and sending
- Document signing
- Video email / hosted video landing pages
- Basic reporting

### Excluded from Core v1

These items should be deferred, hidden, or treated as add-ons until the main product is stable:

- Social DM automation
- Courses / student platform
- Advanced coaching or training features
- Complex multi-step chatbot behavior

### Product Positioning

Position the product as:

> An all-in-one real estate follow-up and conversion system that helps agents capture leads, automate follow-up, send documents, and move prospects to appointment and close.

Do **not** position it as “software that does everything.” Simplicity will help sales.

## Success Criteria

The product is ready for broader launch when:

- A new agent can onboard without direct developer help
- Landing pages can capture leads into the CRM reliably
- Email setup and automations work consistently
- Document signing works end-to-end
- Video email pages work end-to-end
- Team/account data is safely isolated
- Billing and subscriptions are live
- Core workflows are documented and test-covered
- Beta agents actively use it and are willing to pay

## Roadmap Overview

## Phase 1: Product Definition and Scope Lock

**Goal:** Decide exactly what is in v1 and what is not.

### Deliverables

- Final v1 feature list
- Deferred feature list
- Packaging decision for courses and social DM
- Draft pricing structure
- Target beta user profile

### Tasks

- Define the core promise in one sentence
- Confirm the exact feature set included in v1
- Move social DM automation out of the critical path unless proven with Kelly
- Decide whether courses are:
  - hidden admin-only
  - optional add-on
  - removed from marketing entirely
- Define plan structure:
  - solo agent
  - team plan
  - optional add-ons
- Identify the top 3 jobs agents need solved:
  - capture leads
  - follow up automatically
  - send docs and convert faster

### Exit Criteria

- We can explain the product in under 30 seconds
- We have a clear “sell this first” package

## Phase 2: SaaS Foundation and Account Architecture

**Goal:** Harden the app from “custom CRM” into “multi-account SaaS.”

### Deliverables

- Clean tenant/account model strategy
- Role and permission model
- Account settings and team management flow
- Account-aware feature gating

### Tasks

- Audit every app for proper team/account scoping
- Confirm every query respects the current team
- Prevent cross-team data access in views, APIs, uploads, and background jobs
- Define user roles:
  - owner/admin
  - agent
  - optional assistant / ISA later
- Add invitation flow for team members
- Add account/workspace settings area
- Add usage limits where needed:
  - users
  - contacts
  - storage
  - video uploads
  - document sends
- Review media/file access for privacy and tenant isolation

### Exit Criteria

- No feature assumes one internal team
- Permissions are consistent across the product

## Phase 3: Onboarding and Setup Experience

**Goal:** Make setup simple enough for non-technical agents.

### Deliverables

- First-login onboarding wizard
- Setup checklist
- Sample data / templates
- Account readiness dashboard

### Tasks

- Build a guided onboarding flow:
  - create account
  - set profile/team info
  - connect Gmail
  - import contacts or add a first lead
  - create or publish a landing page
  - activate a starter campaign
  - upload first signature template
  - upload or record first video
- Add “getting started” progress indicators
- Create starter templates:
  - buyer lead campaign
  - seller lead campaign
  - open house follow-up
  - simple landing page templates
  - default e-sign template examples
- Add empty-state screens that guide action instead of looking unfinished
- Create a health checklist:
  - email connected
  - domain/base URL configured
  - landing page live
  - campaign active
  - first lead captured

### Exit Criteria

- A beta user can complete setup in one session
- Setup no longer depends on you manually explaining each step

## Phase 4: Core Workflow Reliability

**Goal:** Make the core promises dependable.

### Deliverables

- Stable lead capture flow
- Stable automations
- Stable signatures flow
- Stable video email flow
- Monitoring and alerting for failures

### Tasks

#### Lead Capture

- Test all landing page form submissions
- Confirm API lead creation and assignment logic
- Add error handling and retries where appropriate
- Add notifications for failed form ingestion

#### Email and Automation

- Harden Gmail connect/reconnect flow
- Validate token refresh handling
- Add bounce/failure visibility where possible
- Confirm campaign pauses and reply handling work properly
- Add safe sending controls and rate protections

#### Document Signing

- Test document upload, template prep, sending, signing, and completion
- Add status clarity for senders and signers
- Confirm audit trail and signed PDF generation are reliable

#### Video Email

- Test local and YouTube workflows
- Validate thumbnail, preview GIF, and public page performance
- Confirm tracked links and analytics are correct

#### Background Jobs

- Audit Celery tasks and retries
- Add logging for failed jobs
- Add admin visibility into queue/task failures

### Exit Criteria

- Core workflows work end-to-end without manual intervention
- Failure cases are visible instead of silent

## Phase 5: Billing, Plans, and Packaging

**Goal:** Make it possible to actually charge subscriptions.

### Deliverables

- Billing provider integration
- Subscription model
- Plan enforcement
- Trial and cancellation flow

### Tasks

- Implement Stripe subscriptions
- Add plan definitions:
  - Starter / Solo
  - Team
  - optional add-ons
- Decide how to meter or cap usage
- Add:
  - trial period
  - payment method collection
  - upgrade/downgrade
  - failed payment flow
  - cancellation and retention flow
- Add billing UI:
  - current plan
  - invoices
  - renewal date
  - seat count
- Connect feature access to plan entitlements

### Exit Criteria

- A user can sign up, start trial, add payment info, and remain subscribed without manual handling

## Phase 6: Compliance, Security, and Operations

**Goal:** Reduce legal and operational risk before broader exposure.

### Deliverables

- Terms of service
- Privacy policy
- Support process
- Backups and recovery plan
- Production monitoring

### Tasks

- Draft legal pages:
  - terms
  - privacy
  - acceptable use
- Add consent language to lead capture forms where needed
- Define data deletion/export process
- Review email compliance basics
- Add error monitoring
- Add uptime and worker monitoring
- Set up automated backups
- Test restore process
- Review secrets handling and production settings
- Document incident response basics

### Exit Criteria

- The business has a basic legal and operational backbone

## Phase 7: Beta Program

**Goal:** Learn from real agents before public launch.

### Deliverables

- Beta cohort
- Feedback process
- Bug triage process
- Beta metrics dashboard

### Tasks

- Recruit 5-10 agents:
  - solo agents
  - small team lead
  - one lower-tech user
  - one high-volume follow-up user
- Offer white-glove onboarding at first
- Track onboarding friction closely
- Create a beta feedback cadence:
  - day 3 check-in
  - week 2 check-in
  - end-of-month review
- Collect feedback in 4 buckets:
  - confusing
  - broken
  - valuable
  - worth paying for
- Instrument product usage:
  - time to first lead
  - time to first campaign activation
  - time to first signed document
  - weekly active users
  - support tickets/questions

### Exit Criteria

- Beta users are using the product repeatedly
- At least some beta users say they would pay
- Top recurring friction points are clearly known

## Phase 8: Paid Pilot

**Goal:** Convert the best beta users into early paying customers.

### Deliverables

- Founder pricing
- Sales/demo script
- Referral offer

### Tasks

- Offer discounted founder pricing
- Convert strongest beta users first
- Build a short live demo flow focused on outcomes
- Create a referral incentive for agents who introduce others
- Publish early testimonials and case studies

### Exit Criteria

- The product has real paying users
- Sales messaging is grounded in actual customer outcomes

## Phase 9: Public Launch

**Goal:** Launch a focused brand, website, and repeatable acquisition motion.

### Deliverables

- Marketing website
- Pricing page
- Demo funnel
- Content plan

### Tasks

- Build a marketing site with:
  - homepage
  - features
  - pricing
  - book a demo
  - testimonials / case studies
  - niche landing pages
- Lead with outcomes, not feature overload
- Create a short product demo video
- Publish 3-5 case-study or educational pieces
- Build niche pages such as:
  - CRM for solo real estate agents
  - CRM for small real estate teams
  - automated lead follow-up for Realtors
- Add retargeting only after conversion flow is working

### Exit Criteria

- We can drive traffic to a clear offer with a clear CTA

## Recommended Packaging

### Main Plan

Include:

- CRM
- landing pages
- pipeline
- tasks
- Gmail email automation
- signatures
- video email
- basic reporting

### Add-Ons

- extra seats / teams
- done-for-you setup
- courses / training portal
- advanced templates
- social DM automation later

## Recommended Marketing Strategy

### Initial Motion

Start with founder-led selling, not ads.

- Personal demos
- network referrals
- beta-to-paid conversion
- case studies
- short educational videos

### Best Messaging Angles

- Stop losing leads because follow-up falls through the cracks
- Replace multiple disconnected tools with one workflow
- Capture leads, automate nurture, send docs, and close faster
- Built for real estate agents, not generic sales teams

### Avoid Early

- broad paid advertising
- feature-heavy messaging
- trying to sell every feature to every type of agent

## Priority Order

This should be the actual execution order:

1. Lock v1 scope
2. Audit tenant/account safety
3. Build onboarding/setup flow
4. Harden core workflows
5. Add billing and plan controls
6. Add compliance and ops basics
7. Run beta
8. Convert paid pilot users
9. Launch marketing site and public acquisition

## Immediate Next Sprint Recommendation

The next sprint should focus on the highest-leverage blockers to beta:

1. Write a v1 scope decision doc
2. Audit team scoping across all apps
3. Design onboarding wizard and setup checklist
4. Identify the 3 most fragile core workflows and fix them
5. Define pricing and packaging draft

## Open Decisions

These decisions should be made early because they affect roadmap priority:

- Is social DM officially removed from v1?
- Are courses hidden, kept, or sold as an add-on?
- Is the first paid offer for solo agents only, or solo + teams?
- Will onboarding be self-serve, white-glove, or hybrid during beta?
- Will video hosting default to local, YouTube, or hybrid?

## Working Rule

For every feature decision going forward, ask:

> Does this make it easier for a Realtor to get leads in, automate follow-up, and convert faster?

If not, it should probably wait until after launch.
