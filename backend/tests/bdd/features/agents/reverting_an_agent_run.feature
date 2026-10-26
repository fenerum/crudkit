@transactional @action:AGR.revert
Feature: Reverting an agent run
  Everything a run applied is one change set, so the agent's owner can take
  back a run that went wrong in one step, as long as nobody has changed the
  same fields since.

  Background:
    Given Alice can view and change customers
    And a customer "Acme"
    And Alice has an agent "Fixer" that runs on customers when started by hand
    And the agent "Fixer" applies changes itself

  Scenario: Reverting a run puts back what it changed
    Given the agent's AI will propose changing the name to "Acme Inc"
    And Alice used the "Run now" action on "Fixer"
    When Alice reverts the run of "Fixer" on "Acme"
    Then it succeeds
    And Alice is told "Reverted 1 change(s) made by this run."
    And "Acme" has name "Acme"

  Scenario: Reverting a run removes the notes it added
    Given Alice has permission to delete notes
    And the agent's AI will propose the note "Checked the account."
    When Alice uses the "Run now" action on "Fixer"
    Then the activity of "Acme" is "Checked the account."
    When Alice reverts the run of "Fixer" on "Acme"
    Then it succeeds
    And the activity of "Acme" is empty

  Scenario: A run that changed nothing cannot be reverted
    Given Alice used the "Run now" action on "Fixer"
    When Alice reverts the run of "Fixer" on "Acme"
    Then it is rejected with "This run changed nothing."

  Scenario: A run cannot be reverted once its changes were changed again
    Given the agent's AI will propose changing the name to "Acme Inc"
    And Alice used the "Run now" action on "Fixer"
    And Alice changed the name of "Acme" to "Acme Ltd"
    When Alice reverts the run of "Fixer" on "Acme"
    Then it is rejected with "Not reverted: changed since"
    And "Acme" still has name "Acme Ltd"

  Scenario: A run cannot be reverted twice
    Given the agent's AI will propose changing the name to "Acme Inc"
    And Alice used the "Run now" action on "Fixer"
    And Alice reverted the run of "Fixer" on "Acme"
    When Alice reverts the run of "Fixer" on "Acme"
    Then it is rejected with "already been reverted"
