@endpoint:records.destroy
Feature: Delete records
  Deleting a record takes it out of the app without destroying it, so it can
  be brought back and its history stays intact. The deletion is logged with a
  snapshot of what the record held.

  Background:
    Given Alice can view and delete customers
    And a customer "Acme" with:
      | status | churned        |
      | email  | info@acme.test |

  Scenario: Deleting a record hides it but keeps it
    When Alice deletes "Acme"
    Then it succeeds
    And "Acme" is deleted
    And "Acme" still has status "churned"

  Scenario: A deleted record disappears from the list
    Given a customer "Globex"
    When Alice deletes "Acme"
    And Alice looks at the list of customers
    Then the list holds only "Globex"

  Scenario: A deletion is logged with a snapshot of the record
    When Alice deletes "Acme"
    Then the latest change to "Acme" is a deletion
    And the latest change to "Acme" was made by Alice
    And the deletion of "Acme" kept a snapshot of:
      | name     | Acme           |
      | status   | churned        |
      | email    | info@acme.test |
      | currency | DKK            |
      | deleted  | False          |

  Scenario: A record cannot be deleted twice
    Given Alice deleted "Acme"
    When Alice deletes "Acme"
    Then it is not found

  Scenario: Deleting needs permission to delete records of its type
    Given Bob can view and change customers
    When Bob deletes "Acme"
    Then it is forbidden
    And "Acme" is not deleted
