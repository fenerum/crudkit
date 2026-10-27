@endpoint:changeset_revert
Feature: What an undo puts back, and what it refuses
  An undo puts back everything one change set did, across every record it
  touched, or nothing at all. Creations, deletions, actions and linked
  records each come back their own way, and some changes, such as merges,
  can never be undone.

  Background:
    Given Alice can view, change and delete customers
    And a customer "Acme" with status "active"

  Scenario Outline: Undo puts back the previous <field>
    Given Alice can view topics
    And a topic "Billing"
    And a topic "Support"
    And the <field> of "Acme" is "<before>"
    And Alice changed the <field> of "Acme" to "<after>"
    When Alice undoes that change
    Then it succeeds
    And "Acme" has <field> "<before>"

    Examples:
      | field   | before          | after           |
      | email   | old@acme.test   | new@acme.test   |
      | topic   | Billing         | Support         |
      | balance | 10.00           | 20.00           |

  Scenario: Undoing a change set puts back every record it touched
    Given a customer "Globex" with status "active"
    And Alice changed the status of "Acme" and "Globex" to "churned" in one go
    When Alice undoes that change
    Then it undid 2 changes
    And "Acme" has status "active"
    And "Globex" has status "active"

  Scenario: A conflict on one record stops the whole undo
    Given a customer "Globex" with status "active"
    And Bob can view and change customers
    And Alice changed the status of "Acme" and "Globex" to "churned" in one go
    And Bob changed the status of "Globex" to "active"
    When Alice undoes her change
    Then the undo conflicts on the status of "Globex"
    And "Acme" still has status "churned"

  Scenario: Undoing the creation of a record deletes it
    Given Alice can add customers
    And Alice added a new customer "Fresh"
    When Alice undoes that change
    Then it succeeds
    And "Fresh" is deleted

  Scenario: Undoing a creation needs permission to delete
    Given Bob can view, add and change customers
    And Bob added a new customer "Fresh"
    When Bob undoes that change
    Then it is forbidden
    And "Fresh" is not deleted

  Scenario: Undoing an action puts back what it changed
    Given Alice used the "Mark churned" action on "Acme"
    When Alice undoes that change
    Then it succeeds
    And "Acme" has status "active"
    And the latest change to "Acme" is an undo

  Scenario: Undoing an action needs permission to run it
    Given Dave is a superuser
    And only superusers may run "Mark churned"
    And Dave used the "Mark churned" action on "Acme"
    When Alice undoes that change
    Then it is forbidden
    And "Acme" still has status "churned"

  Scenario: An action that has since been renamed cannot be undone
    Given Alice used the "Mark churned" action on "Acme"
    And the "Mark churned" action has since been renamed
    When Alice undoes that change
    Then it is forbidden
    And "Acme" still has status "churned"

  Scenario: Undo puts back a ticket's watchers
    Given Alice can view and change tickets
    And a ticket "Printer broken"
    And a customer "Globex"
    And "Acme" is a watcher of "Printer broken"
    And Alice added "Globex" to the watchers of "Printer broken"
    When Alice undoes that change
    Then it succeeds
    And the watchers of "Printer broken" are "Acme"
    And the latest change to "Printer broken" is an undo

  Scenario: Undoing a watcher change conflicts when the watchers changed since
    Given Alice can view and change tickets
    And a ticket "Printer broken"
    And Bob can view and change tickets
    And a customer "Globex"
    And Alice added "Acme" to the watchers of "Printer broken"
    And Bob added "Globex" to the watchers of "Printer broken"
    When Alice undoes her change
    Then the undo conflicts on the watchers of "Printer broken"
    And the watchers of "Printer broken" are "Acme" and "Globex"

  Scenario: Undo is refused when the record's own rules no longer allow the old value
    Given Alice changed the name of "Acme" to "Acme Inc"
    And customers now refuse the name "Acme"
    When Alice undoes that change
    Then it is rejected with "Could not revert"
    And "Acme" still has name "Acme Inc"

  Scenario: Undoing a delete conflicts when the record was brought back since
    Given Alice deleted "Acme"
    And "Acme" was restored afterwards
    When Alice undoes that change
    Then the undo conflicts because "Acme" is no longer deleted

  Scenario: Undo conflicts when the record has since been removed for good
    Given Alice changed the status of "Acme" to "churned"
    And "Acme" was removed for good afterwards
    When Alice undoes that change
    Then the undo conflicts because "Acme" no longer exists

  Scenario: Forcing an undo skips records that no longer exist
    Given Alice changed the status of "Acme" to "churned"
    And "Acme" was removed for good afterwards
    When Alice undoes that change anyway
    Then it undid 0 changes

  Scenario: A merge cannot be undone
    Given a customer "Acme copy"
    And Alice merged the duplicate "Acme copy" into "Acme"
    When Alice undoes that change
    Then it is rejected with "Merges cannot be reverted"
    And "Acme copy" is deleted

  Scenario: Changes recorded before undo existed cannot be undone
    Given Alice changed the status of "Acme" to "churned"
    And the change log of that change predates undo
    When Alice undoes that change
    Then it is rejected with "recorded before undo was available"
    And "Acme" still has status "churned"

  Scenario: Undoing needs a signed-in person
    Given Alice changed the status of "Acme" to "churned"
    When someone who is not signed in undoes that change
    Then it requires signing in
    And "Acme" still has status "churned"
