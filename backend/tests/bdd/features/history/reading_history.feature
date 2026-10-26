@endpoint:records.history @type:CHG
Feature: Read a record's history
  The History tab of a record lists its change sets, newest first: who made
  each one, where it came from, what it did and whether it can still be undone.
  Because the log keeps old values, reading it needs its own permission on top
  of being allowed to see the record.

  Background:
    Given Alice can view and change customers
    And Alice can view change logs
    And a customer "Acme" with status "active"

  Scenario: The history lists change sets newest first, with who made them and where
    Given Alice changed the name of "Acme" to "Acme Inc"
    And a background job changed the status of "Acme" to "churned"
    When Alice reads the history of "Acme"
    Then it succeeds
    And the history reads, newest first:
      | by         | from       | did     |
      | the system | the system | Updated |
      | Alice      | the app    | Updated |
    And the newest change set in the history changed the status from "active" to "churned"

  Scenario: The history shows the name of the action that was run
    Given Alice used the "Mark churned" action on "Acme"
    When Alice reads the history of "Acme"
    Then the history reads, newest first:
      | by    | from    | did           |
      | Alice | the app | Ran an action |
    And the newest change set in the history is labelled "Mark churned"

  Scenario: A change can be undone from the history until it has been undone
    Given Alice changed the status of "Acme" to "churned"
    When Alice reads the history of "Acme"
    Then the newest change set in the history can be undone

  Scenario: An undone change is marked as undone and the undo is listed above it
    Given Alice changed the status of "Acme" to "churned"
    And Alice undid that change
    When Alice reads the history of "Acme"
    Then the history reads, newest first:
      | by    | from     | did               |
      | Alice | an undo  | Reverted a change |
      | Alice | the app  | Updated           |
    And the second change set in the history is marked as undone
    And the second change set in the history cannot be undone
    And the newest change set in the history can be undone

  Scenario: The history says how many other records a change set touched
    Given a customer "Globex" with status "active"
    And Alice changed the status of "Acme" and "Globex" to "churned" in one go
    When Alice reads the history of "Acme"
    Then the newest change set in the history also changed 1 other record

  Scenario: A merge shows in the history but cannot be undone from it
    Given a customer "Acme copy"
    And Alice merged the duplicate "Acme copy" into "Acme"
    When Alice reads the history of "Acme"
    Then the history reads, newest first:
      | by    | from    | did    |
      | Alice | the app | Merged |
    And the newest change set in the history cannot be undone

  Scenario: The history of a deleted record can still be read
    Given Alice can delete customers
    And Alice deleted "Acme"
    When Alice reads the history of "Acme"
    Then it succeeds
    And the history reads, newest first:
      | by    | from    | did     |
      | Alice | the app | Deleted |

  Scenario: Changes logged before change sets existed are listed one by one and cannot be undone
    Given "Acme" has 2 changes logged before change sets existed
    When Alice reads the history of "Acme"
    Then the history has 2 change sets
    And every change set in the history has a single entry
    And no change set in the history can be undone

  Scenario: The history shows at most the 200 most recent changes
    Given "Acme" has been changed 205 times
    When Alice reads the history of "Acme"
    Then the history has 200 change sets
    And the newest change set in the history changed the name from "Acme 203" to "Acme 204"

  Scenario: Reading the history needs permission to view the change log
    Given Bob can view customers
    When Bob reads the history of "Acme"
    Then it is forbidden with "You may not view change history."

  Scenario: Reading the history needs permission to see the record
    Given Carol can view change logs
    When Carol reads the history of "Acme"
    Then it is forbidden
