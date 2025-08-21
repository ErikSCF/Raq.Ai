**“ Coach Connect” App – Functional Scope Document Prepared For:** Developer Quoting and Scoping Purposes **Date:** July 2025

1. # **Project Overview**

Coach Connect is a mobile and web-based platform designed to help high school and club sports coaches understand and develop their athletes using personality-based insights. The platform will centralize individualized player profiles, coaching recommendations, team dashboards, calendars, and developmental tracking into a single, easy-to-use tool.

This app is not intended for player use. It is built for coaches, athletic directors, club directors, and internal administrative users. The goal is to equip coaching staff with  
meaningful, personalized insights that improve athlete support, motivation, and leadership development.

2. # **Users and Access**

   Primary Users:

* High school coaches

* Club team coaches

* Athletic directors

* Club directors Admin Users:

* Internal administrative staff responsible for managing users, teams, and content

  Access Rules:

* Only coaches, directors, and admins will have login access

* Users will only be able to view teams and players assigned to them

* Players will take the assessment, but will not have access to the platform

3. # **Functional Requirements**

   1. *Player Profiles*

      * Each player profile will include:

      * A manually entered summary created from an external personality assessment (e.g., PeopleKeys DiSC)

      * Key attributes such as communication style, motivators, behavioral tendencies, and stress responses  
      * Tags for grade level, position, team level (e.g., JV/Varsity), and leadership roles

      * Collapsible and expandable views for fast scanning in practice or game environments  
      * Assessment data will not be imported or integrated automatically at this

      stage. Admin users will manually enter the relevant player insight based on assessment reports.

   2. *Team Overview*

      * Each user will be able to:

        * View all players on a team in a grid or card format

        * Filter and sort players by:

          * Assessment attributes (e.g., communication style)

          * Grade level, role, or position

          * Leadership status or custom tags

        * See a visual representation of team composition based on player characteristics

   3. *Practice and Game Management*

      * Users must be able to:

        * Create and categorize events (practices, games, meetings, etc.)

      * Enter:

        * Event name

        * Date and time

        * Location (must integrate with Google Maps for directions)

        * Notes or agenda

        * View events in calendar formats (daily, weekly, monthly)

        * Log event-specific player observations or notes

   4. *Coaching Support Engine*

      * Users must be able to:

        * Select a player and choose from a list of coaching needs or questions (e.g., “How do I challenge this player today?”)

        * Receive tailored coaching suggestions based on the player's profile

        * Access strategies for:

          * Motivation

          * Feedback and praise

          * Conflict or stress

          * Accountability and discipline

      * Coaching recommendations will be powered by an AI model trained on insight methodology and content provided by our team. We will supply the foundational psychology, decision logic, and coaching framework; the developer is expected to implement an AI system that can deliver intelligent suggestions based on this content.

   5. *Note Logging and Player Tracking*

      * Users must be able to:

        * Log notes for players tied to specific dates or events

        * Tag notes with custom categories (e.g., leadership, communication, effort)

        * View a chronological note history per player

        * Generate and export PDF reports summarizing player growth, coach observations, and key traits

   6. *Admin Dashboard (Web-Based)*

      * Admin users must be able to:

        * Create and manage user accounts (coaches, directors)

        * Build team rosters and assign players

        * Manually input or edit player profile content based on assessment results

        * Upload and manage coaching content and templates used by the AI engine

        * Control user permissions and team visibility

        * The admin dashboard must be accessible via standard web browsers.

   7. *Communication Tools (Non-Messaging)*

      * The app will not include in-app messaging

      * Instead, it will allow users to copy prewritten communication templates to clipboard for use in external apps (e.g., email or text)  
      * Push notifications may be sent to coaches and directors for:

        * Event reminders

        * Suggested coaching actions or insights

        * Prompts to review or update player information

   8. *AI Coaching Suggestions*

      * The app must include an AI-based suggestion system that:

        * Generates coaching tips based on player traits and coach-entered activity

        * Learns from usage patterns over time

        * Surfaces context-aware guidance (e.g., based on event type or recent notes)

        * Is trained using methodology, insight structure, and content provided by our internal team

      * The development team will be responsible for implementing the AI system and advising on the appropriate models, platforms, and architecture to support this functionality.

4. # **User Experience and Design Guidelines**

* Clean, modern, mobile-first design

* Minimalist interface optimized for use during practices, games, and team meetings

* Expected UX flow:

  * Player access within 2–3 taps

  * Swipe or scroll team view

  * Tap-to-expand profile insights and recommendations

  * Simple data entry forms for logging notes and creating events

* The web-based admin dashboard should follow the same aesthetic and be optimized for keyboard and mouse interactions

5. # **Content and Data Management**

* All assessment insights, coaching content, and methodology will be developed by our team  
* Admin users will be responsible for inputting and updating all player profiles and templates  
* Coaches and directors will only see content relevant to their assigned teams and players

6. # **Timeline Expectations**

A functional, interactive prototype must be delivered by the end of Q1 2026\.

The prototype should demonstrate real user flows and be suitable for live feedback from coaches.