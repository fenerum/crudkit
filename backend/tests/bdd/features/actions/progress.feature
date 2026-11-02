@type:JOB @endpoint:records.action
Feature: Follow a long-running action's progress
  Some actions take a while: recalculating every invoice, importing a mailbox.
  The person who runs one sees how far it got, live, while it works, whether
  it finishes during the click or carries on in the background. Each run is
  kept as a task they can look back on; nobody else sees it.

  Background:
    Given Alice can view and change customers
    And Bob can view and change customers
    And a customer "Acme"

  Scenario: An action that reports progress leaves a finished task
    Given customers have an action "Recount" that works through 3 steps
    When Alice uses the "Recount" action on "Acme"
    Then it succeeds
    And Alice's task "Recount" has succeeded with 3 of 3 steps done

  @transactional @websocket:ws/changes/
  Scenario: The person who ran the action hears every step as it happens
    Given customers have an action "Recount" that works through 3 steps
    And Alice is watching the change stream
    And Bob is watching the change stream
    When Alice uses the "Recount" action on "Acme"
    Then Alice hears her task "Recount" go through 1 of 3, 2 of 3 and 3 of 3 and succeed
    And Bob hears nothing

  Scenario: An action that gives up leaves its task failed with the reason
    Given customers have an action "Rebalance" that gives up with "Ledger locked" after 1 step
    When Alice uses the "Rebalance" action on "Acme"
    Then it is rejected with "Ledger locked"
    And Alice's task "Rebalance" has failed with "Ledger locked"

  Scenario: An action that reports no progress leaves no task behind
    Given customers have an action "Check credit" that answers "Credit OK"
    When Alice uses the "Check credit" action on "Acme"
    Then Alice gets the answer "Credit OK"
    And Alice has no tasks

  Scenario: A task handed to the background keeps running after the action returns
    Given customers have an action "Import mail" that hands its task to the background
    When Alice uses the "Import mail" action on "Acme"
    Then it succeeds
    And Alice's task "Import mail" is still running

  Scenario: A task handed to the background finishes there
    Given customers have an action "Import mail" that hands its task to the background
    And Alice used the "Import mail" action on "Acme"
    When the background task works through 2 steps
    Then Alice's task "Import mail" has succeeded with 2 of 2 steps done

  Scenario: A task that fails in the background is recorded as failed
    Given customers have an action "Import mail" that hands its task to the background
    And Alice used the "Import mail" action on "Acme"
    When the background task fails with "Mailbox full"
    Then Alice's task "Import mail" has failed with "Mailbox full"

  Scenario: People see their own tasks and nobody else's
    Given customers have an action "Recount" that works through 3 steps
    And Alice used the "Recount" action on "Acme"
    Then Alice sees the task "Recount" in her list of tasks
    And Bob cannot see Alice's task "Recount"
