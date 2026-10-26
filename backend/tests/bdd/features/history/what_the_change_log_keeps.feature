@type:CHG
Feature: What the change log keeps
  For every change the log keeps each changed field's value before and after,
  so anyone can see exactly what happened and undo it. Bookkeeping such as
  timestamps is left out, values that only look different are not counted as
  changes, and a deleted record leaves a snapshot of what it held.

  Background:
    Given Alice can view and change customers
    And a customer "Acme" with status "active"

  Scenario: Only the fields that changed are logged
    When Alice changes the name of "Acme" to "Acme Inc"
    Then the latest change to "Acme" is an update
    And the latest change to "Acme" changed only the name
    And the latest change to "Acme" changed the name from "Acme" to "Acme Inc"

  Scenario: A link to another record is logged as that record
    Given a topic "Billing"
    When Alice changes the topic of "Acme" to "Billing"
    Then the latest change to "Acme" changed the topic from "" to "Billing"

  Scenario: Writing the same amount in another form is not a change
    Given the balance of "Acme" is "12.50"
    When Alice changes the balance of "Acme" to "12.5"
    Then it succeeds
    And the latest change to "Acme" changed nothing

  Scenario: A new record is logged as a creation with everything it was given
    Given Alice can add customers
    When Alice adds a new customer "Fresh"
    Then the latest change to "Fresh" is a creation
    And the latest change to "Fresh" changed the name from "" to "Fresh"
    And the latest change to "Fresh" was made by Alice

  Scenario: Deleting a record keeps a snapshot of what it held
    Given Bob can view and delete customers
    And the email of "Acme" is "hello@acme.test"
    When Bob deletes "Acme"
    Then the deletion of "Acme" kept a snapshot of:
      | name     | Acme            |
      | email    | hello@acme.test |
      | status   | active          |
      | currency | DKK             |
      | deleted  | False           |
    And the latest change to "Acme" was made by Bob

  Scenario: Running an action is logged with the action's name and what it changed
    When Alice uses the "Mark churned" action on "Acme"
    Then it succeeds
    And the latest change to "Acme" is an action
    And the latest change to "Acme" is labelled "Mark churned"
    And the latest change to "Acme" changed the status from "active" to "churned"
    And the app is told the change set of the latest change to "Acme"

  Scenario: Adding a watcher to a ticket is logged with the watchers before and after
    Given a ticket "Printer broken"
    And a customer "Globex"
    And "Globex" is a watcher of "Printer broken"
    When Alice adds "Acme" to the watchers of "Printer broken"
    Then the latest change to "Printer broken" is an update
    And the latest change to "Printer broken" changed the watchers from "Globex" to "Acme and Globex"
    And the latest change to "Printer broken" came from the app
    And the latest change to "Printer broken" was made by Alice

  Scenario: Removing a watcher from a ticket is logged
    Given a ticket "Printer broken"
    And "Acme" is a watcher of "Printer broken"
    When Alice removes "Acme" from the watchers of "Printer broken"
    Then the latest change to "Printer broken" changed the watchers from "Acme" to ""

  Scenario: Adding someone who already watches a ticket logs nothing
    Given a ticket "Printer broken"
    And Alice added "Acme" to the watchers of "Printer broken"
    When Alice adds "Acme" to the watchers of "Printer broken"
    Then the change log of "Printer broken" has 1 entry
