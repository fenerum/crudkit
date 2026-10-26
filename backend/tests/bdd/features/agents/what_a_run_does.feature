@transactional @type:AGR @action:AGT.run_now
Feature: What an agent run does
  Each run hands one record to the assistant together with the agent's
  instructions. What the agent wants to change is filed as proposals for a
  person to confirm or, when the agent applies changes itself, carried out
  straight away, except for changes that always need a person's approval.

  Background:
    Given Alice can view and change customers
    And a customer "Acme"
    And Alice has an agent "Fixer" that runs on customers when started by hand

  Scenario: A run carries out the agent's instructions on the record
    When Alice uses the "Run now" action on "Fixer"
    Then the latest run of "Fixer" succeeded
    And the agent "Fixer" was given its instructions
    And the agent was asked to work on "Acme", which was picked by hand

  Scenario: An agent proposes its changes for a person to confirm
    Given the agent's AI will propose changing the name to "Acme Inc"
    When Alice uses the "Run now" action on "Fixer"
    Then the agent "Fixer" proposed changing the name of "Acme" to "Acme Inc"
    And "Acme" still has name "Acme"

  Scenario: An agent that applies changes itself changes the record as the agent
    Given the agent "Fixer" applies changes itself
    And the agent's AI will propose changing the name to "Acme Inc"
    When Alice uses the "Run now" action on "Fixer"
    Then "Acme" has name "Acme Inc"
    And the change to "Acme" is credited to the agent "Fixer"

  Scenario: An agent that applies changes itself still leaves changes that need approval to a person
    Given changes to the email of customers need a person's approval
    And the agent "Fixer" applies changes itself
    And the agent's AI will propose changing the name to "Acme Inc"
    And the agent's AI will propose changing the email to "ceo@acme.test"
    When Alice uses the "Run now" action on "Fixer"
    Then "Acme" has name "Acme Inc"
    And "Acme" has email ""
    And the agent "Fixer" proposed changing the email of "Acme" to "ceo@acme.test"

  Scenario: Run now starts a run on every record the agent works on
    Given a customer "Beta"
    When Alice uses the "Run now" action on "Fixer"
    Then Alice is told "Started 2 runs of Fixer."
    And the agent "Fixer" ran on "Acme"
    And the agent "Fixer" ran on "Beta"

  Scenario: Run now only takes the records in the agent's saved view
    Given a customer "Beta"
    And the agent "Fixer" only works on customers named "Acme"
    When Alice uses the "Run now" action on "Fixer"
    Then Alice is told "Started 1 run of Fixer."
    And the agent "Fixer" did not run on "Beta"

  Scenario: Run now takes the records the agent has waited longest to work on first
    Given a customer "Beta"
    And the agent "Fixer" works on at most 1 record per run
    And the agent "Fixer" has already worked on "Beta"
    When Alice uses the "Run now" action on "Fixer"
    Then Alice is told "Started 1 run of Fixer."
    And the latest run of "Fixer" was on "Acme"

  Scenario: Run now starts no more runs than are left for the day
    Given a customer "Beta"
    And the agent "Fixer" may run at most 3 times a day
    And the agent "Fixer" already ran 2 times today
    When Alice uses the "Run now" action on "Fixer"
    Then Alice is told "Started 1 run of Fixer."

  Scenario: The runs of a turned-off agent fail
    Given the agent "Fixer" is turned off
    When Alice uses the "Run now" action on "Fixer"
    Then the latest run of "Fixer" failed with "The agent is disabled."

  Scenario: Runs fail when no AI model is configured
    Given no AI model is configured
    When Alice uses the "Run now" action on "Fixer"
    Then the latest run of "Fixer" failed with "No AI model is configured."

  Scenario: A run that cannot be handed to the background workers is marked as failed
    Given the background task queue is unreachable
    When Alice uses the "Run now" action on "Fixer"
    Then it succeeds
    And the latest run of "Fixer" failed with "Could not queue the run: Connection refused"
