@endpoint:widgets-list
Feature: The dashboard
  The home page shows a dashboard of widgets the project chooses for each
  person: short lists of records, charts and embedded Metabase questions. A
  misconfigured dashboard shows nothing rather than breaking the home page.

  Background:
    Given Alice is a user without any permissions

  Scenario: Without a dashboard the home page has no widgets
    Given the dashboard is not set up
    When Alice opens the dashboard
    Then the dashboard is empty

  Scenario: A dashboard that cannot be loaded shows no widgets
    Given the dashboard is set up with something that does not exist
    When Alice opens the dashboard
    Then the dashboard is empty

  Scenario: The dashboard shows the project's widgets in order
    Given the dashboard shows a list of churned customers
    And the dashboard shows a chart of signups
    When Alice opens the dashboard
    Then the dashboard shows "Churned customers" and "Signups"

  Scenario: A list widget says which records to show and how
    Given the dashboard shows a list of churned customers
    When Alice opens the dashboard
    Then the widget "Churned customers" is a list widget 2 columns wide
    And the widget "Churned customers" lists up to 3 customers whose status is "churned"
    And the widget "Churned customers" shows the fields name and owner

  Scenario: A chart widget gives the data to draw
    Given the dashboard shows a chart of signups
    When Alice opens the dashboard
    Then the widget "Signups" is a chart widget 1 column wide
    And the widget "Signups" draws a line chart of "Signups"

  Scenario: A chart whose data fails to load shows the error instead
    Given the dashboard shows a chart that fails to load
    When Alice opens the dashboard
    Then the widget "Broken chart" draws a bar chart explaining "Error: no data"

  Scenario: A Metabase question is embedded with a link that soon expires
    Given Metabase is connected
    And the dashboard shows a Metabase question about revenue
    When Alice opens the dashboard
    Then the widget "Revenue" is a metabase widget 1 column wide
    And the widget "Revenue" embeds Metabase question 7 with a link that expires in 10 minutes

  Scenario: A Metabase question without Metabase connected explains what is missing
    Given the dashboard shows a Metabase question about revenue
    When Alice opens the dashboard
    Then the widget "Revenue" explains "METABASE_SECRET_KEY / METABASE_SITE_URL not set in settings."

  Scenario: The dashboard needs signing in
    When someone who is not signed in opens the dashboard
    Then it requires signing in
