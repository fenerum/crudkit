@transactional
Feature: What starts an agent
  An agent can get to work by itself whenever a record of its type is created
  or changed through the app, so follow-up work happens without anyone
  remembering to do it. Limits keep a burst of edits from setting it off again
  and again.

  Background:
    Given Alice can view and change customers
    And a customer "Acme"
    And a customer "Beta"
    And Alice has an agent "Renamer" that runs when the status of a customer changes

  Scenario: Changing a watched field starts the agent on that record
    When Alice changes the status of "Acme" to "churned"
    Then the agent "Renamer" ran on "Acme"
    And the agent "Renamer" did not run on "Beta"
    And the agent was asked to work on "Acme", which just changed (status)

  Scenario: Changing a field the agent does not watch does not start it
    When Alice changes the name of "Acme" to "Acme Inc"
    Then the agent "Renamer" did not run

  Scenario: An agent that watches no particular field starts on any change
    Given Alice has an agent "Tidier" that runs whenever a customer changes
    When Alice changes the name of "Acme" to "Acme Inc"
    Then the agent "Tidier" ran on "Acme"

  Scenario: An action that changes a watched field starts the agent
    When Alice uses the "Mark churned" action on "Acme"
    Then the agent "Renamer" ran on "Acme"

  Scenario: Creating a record starts the agents that wait for new records
    Given Alice can add customers
    And Alice has an agent "Welcomer" that runs when a customer is created
    When Alice creates a customer "Gamma"
    Then the agent "Welcomer" ran on "Gamma"
    And the agent was asked to work on "Gamma", which was just created
    And the agent "Renamer" did not run

  Scenario: Editing a record does not start the agents that wait for new records
    Given Alice has an agent "Welcomer" that runs when a customer is created
    When Alice changes the status of "Acme" to "churned"
    Then the agent "Welcomer" did not run

  Scenario: A turned-off agent does not start
    Given the agent "Renamer" is turned off
    When Alice changes the status of "Acme" to "churned"
    Then the agent "Renamer" did not run

  Scenario: Changes saved outside the app do not start agents
    Given the status of "Acme" is "churned"
    Then the agent "Renamer" did not run

  Scenario: Changes made by an agent never start agents
    Given the agent "Renamer" applies changes itself
    And the agent's AI will propose changing the name to "Acme Inc"
    And Alice has an agent "Tidier" that runs when the name of a customer changes
    When Alice changes the status of "Acme" to "churned"
    Then "Acme" has name "Acme Inc"
    And the agent "Renamer" ran once
    And the agent "Tidier" did not run

  Scenario: An agent only works on the records in its saved view
    Given the agent "Renamer" only works on customers named "Acme"
    When Alice changes the status of "Beta" to "churned"
    Then the agent "Renamer" did not run

  Scenario: An agent only works on records the person it runs as can see
    Given Carol is a user without any permissions
    And Carol has an agent "Snoop" that runs when the status of a customer changes
    When Alice changes the status of "Acme" to "churned"
    Then the agent "Snoop" did not run
    And the agent "Renamer" ran on "Acme"

  Scenario Outline: A record already waiting for the agent is not queued again
    Given a run of "Renamer" on "Acme" has been <state> for <minutes> minutes
    When Alice changes the status of "Acme" to "churned"
    Then the agent "Renamer" ran <times> on "Acme"

    Examples:
      | state   | minutes | times |
      | queued  | 10      | once  |
      | running | 10      | once  |
      | queued  | 90      | twice |

  Scenario: An agent stops starting once it has used up its runs for the day
    Given the agent "Renamer" may run at most 1 time a day
    When Alice changes the status of "Acme" to "churned"
    And Alice changes the status of "Beta" to "churned"
    Then the agent "Renamer" ran on "Acme"
    And the agent "Renamer" did not run on "Beta"
