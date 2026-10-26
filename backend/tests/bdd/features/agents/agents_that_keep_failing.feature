@transactional
Feature: Agents that keep failing are turned off
  An agent whose runs fail three times in a row is turned off, with a note on
  the agent saying why, so a broken agent does not keep failing unnoticed.
  Turning it back on gives it a fresh start.

  Background:
    Given Alice can view and change customers
    And a customer "Acme"
    And Alice has an agent "Fixer" that runs on customers when started by hand

  Scenario: Three failed runs in a row turn the agent off
    Given the agent's AI is down
    When Alice uses the "Run now" action on "Fixer" 3 times
    Then the agent "Fixer" is turned off
    And the latest run of "Fixer" failed with "The model is down"
    And the activity of "Fixer" is "Disabled after 3 failed runs in a row. Last error: The model is down"

  Scenario: Fewer than three failed runs leave the agent on
    Given the agent's AI is down
    When Alice uses the "Run now" action on "Fixer" 2 times
    Then the agent "Fixer" is turned on
    And the agent "Fixer" has 2 failures in a row

  Scenario: A successful run clears the failure streak
    Given the agent's AI is down
    And Alice used the "Run now" action on "Fixer" 2 times
    And the agent's AI is back
    When Alice uses the "Run now" action on "Fixer"
    Then the agent "Fixer" has no failures in a row
    And the agent "Fixer" is turned on

  Scenario: Turning an agent back on gives it a fresh start
    Given the agent "Fixer" was switched off after 3 failed runs in a row
    When Alice turns the agent "Fixer" back on
    Then it succeeds
    And the agent "Fixer" is turned on
    And the agent "Fixer" has no failures in a row

  Scenario: Failed dry runs do not count towards turning the agent off
    Given the agent's AI is down
    When Alice uses the "Dry run on latest matching record" action on "Fixer" 3 times
    Then the agent "Fixer" is turned on
    And the agent "Fixer" has no failures in a row
