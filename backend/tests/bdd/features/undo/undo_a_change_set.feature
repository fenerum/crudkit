@endpoint:changeset_revert
Feature: Undo a change
  Every save is recorded as a change set: everything one click, one API call
  or one assistant proposal changed together. Anyone allowed to make the
  original change can undo the whole set in one step, as long as nobody has
  changed the same fields since.

  Background:
    Given Alice can view, change and delete customers
    And a customer "Acme" with status "active"

  Scenario: Undoing an edit puts the previous value back
    Given Alice changed the status of "Acme" to "churned"
    When Alice undoes that change
    Then it succeeds
    And "Acme" has status "active"

  Scenario: Undoing a delete brings the record back
    Given Alice deleted "Acme"
    When Alice undoes that change
    Then it succeeds
    And "Acme" is not deleted

  Scenario: An undo is itself a change that can be undone
    Given Alice changed the status of "Acme" to "churned"
    And Alice undid that change
    When Alice undoes that change
    Then it succeeds
    And "Acme" has status "churned"

  Scenario: Undo is blocked when someone changed the same field afterwards
    Given Bob can view and change customers
    And Alice changed the status of "Acme" to "churned"
    And Bob changed the status of "Acme" to "active"
    When Alice undoes her change
    Then the undo conflicts on the status of "Acme"
    And "Acme" still has status "active"

  Scenario: Undo can be forced over a conflicting change
    Given Bob can view and change customers
    And Alice changed the name of "Acme" to "Acme Inc"
    And Bob changed the name of "Acme" to "Acme Ltd"
    When Alice undoes her change anyway
    Then it succeeds
    And "Acme" has name "Acme"

  Scenario: The same change cannot be undone twice
    Given Alice changed the status of "Acme" to "churned"
    And Alice undid that change
    When Alice tries to undo the same change again
    Then it is rejected with "already been reverted"

  Scenario: Undoing needs the same permission as the original change
    Given Carol can view customers
    And Alice changed the status of "Acme" to "churned"
    When Carol undoes that change
    Then it is forbidden
    And "Acme" has status "churned"

  Scenario: A change that never happened cannot be undone
    When Alice undoes a change that never happened
    Then it is not found
