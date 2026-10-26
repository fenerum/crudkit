@endpoint:records.update @endpoint:records.partial_update
Feature: Edit records
  People allowed to change a record can edit one field at a time or save the
  whole form. Every change is checked against the type's rules, recorded with
  who made it, and logged with what changed.

  Background:
    Given Alice can view and change customers
    And a customer "Acme" with:
      | status | active        |
      | email  | info@acme.test |

  Scenario: Changing one field leaves the others as they were
    When Alice changes the status of "Acme" to "churned"
    Then it succeeds
    And "Acme" has status "churned"
    And "Acme" still has email "info@acme.test"

  Scenario: The person who changed a record last is recorded
    When Alice changes the status of "Acme" to "churned"
    Then Alice is recorded as the last editor of "Acme"

  Scenario: A change is logged with the old and the new value
    When Alice changes the status of "Acme" to "churned"
    Then the latest change to "Acme" is an update
    And the latest change to "Acme" was made by Alice
    And the latest change to "Acme" changed the status from "active" to "churned"

  Scenario: Saving the whole form replaces the values it sends
    When Alice replaces "Acme" with:
      | name   | Acme Inc |
      | status | churned  |
    Then it succeeds
    And "Acme" has name "Acme Inc"
    And "Acme" has status "churned"
    And "Acme" still has email "info@acme.test"

  Scenario: Saving the whole form needs every required field
    When Alice replaces "Acme" with:
      | status | churned |
    Then it is rejected with "This field is required."
    And "Acme" still has status "active"

  Scenario: A change that breaks the field's rules is refused
    When Alice changes the status of "Acme" to "bankrupt"
    Then it is rejected with "is not a valid choice"
    And "Acme" still has status "active"

  @known-bug
  Scenario: Linking to a record that does not exist is refused and keeps the old link
    Given Alice can view topics
    And a topic "Billing"
    And the topic of "Acme" is "Billing"
    When Alice points the topic of "Acme" at a topic that does not exist
    Then it is rejected with "not found"
    And "Acme" still has topic "Billing"

  @known-bug
  Scenario: A link to a record the person may not see is refused as if it did not exist
    Given a topic "Billing"
    And a topic "Internal"
    And the topic of "Acme" is "Billing"
    When Alice changes the topic of "Acme" to "Internal"
    Then it is rejected with "not found"
    And "Acme" still has topic "Billing"

  @known-bug
  Scenario: A link only accepts a record of the type it points at
    Given Alice can view topics
    And a topic "Billing"
    And a customer "Globex"
    And the topic of "Acme" is "Billing"
    When Alice changes the topic of "Acme" to "Globex"
    Then it is rejected
    And "Acme" still has topic "Billing"

  Scenario: Who created a record cannot be changed
    Given Alice owns a customer "Globex"
    And Bob is a user without any permissions
    When Alice changes the created by of "Globex" to "Bob"
    Then Alice is recorded as the creator of "Globex"

  Scenario: Editing needs permission to change records of its type
    Given Bob can view customers
    When Bob changes the status of "Acme" to "churned"
    Then it is forbidden
    And "Acme" still has status "active"

  Scenario: A deleted record can no longer be edited
    Given Alice can delete customers
    And Alice deleted "Acme"
    When Alice changes the status of "Acme" to "churned"
    Then it is not found
