@transactional @action:AGT.dry_run
Feature: Trying out an agent with a dry run
  A dry run shows what an agent would do with the newest record it works on,
  without changing or filing anything, so its owner can tune the instructions
  safely before letting it loose.

  Background:
    Given Alice can view and change customers
    And a customer "Acme"
    And a customer "Beta"
    And Alice has an agent "Fixer" that runs on customers when started by hand
    And the agent "Fixer" applies changes itself

  Scenario: A dry run shows what the agent would change without changing it
    Given the agent's AI will propose changing the name to "Beta Inc"
    When Alice uses the "Dry run on latest matching record" action on "Fixer"
    Then it succeeds
    And the dry run of "Fixer" on "Beta" would have changed the name to "Beta Inc"
    And "Beta" still has name "Beta"
    And the agent "Fixer" left no proposals

  Scenario: The agent is told that it is on a dry run
    When Alice uses the "Dry run on latest matching record" action on "Fixer"
    Then the agent was asked to work on "Beta", which was picked by hand
    And the agent was told that nothing it proposes will be saved

  Scenario: A dry run needs a record for the agent to work on
    Given the agent "Fixer" only works on customers named "Nobody"
    When Alice uses the "Dry run on latest matching record" action on "Fixer"
    Then it is rejected with "No record matches this agent."
    And the agent "Fixer" did not run

  Scenario: A turned-off agent can still be tried out
    Given the agent "Fixer" is turned off
    When Alice uses the "Dry run on latest matching record" action on "Fixer"
    Then the latest run of "Fixer" succeeded

  Scenario: Dry runs do not use up the agent's runs for the day
    Given the agent "Fixer" may run at most 1 time a day
    And Alice used the "Dry run on latest matching record" action on "Fixer"
    When Alice uses the "Run now" action on "Fixer"
    Then Alice is told "Started 1 run of Fixer."
