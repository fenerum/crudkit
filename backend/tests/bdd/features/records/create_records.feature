@endpoint:records.create
Feature: Create records
  Anyone allowed to add records of a type can create them from the app. The
  app records who created each record, can start a record already linked to
  the page it was created from, and checks the type's own rules before saving.

  Background:
    Given Alice can view and add customers

  Scenario: Creating a record saves it and records who created it
    When Alice creates a customer "Acme"
    Then it succeeds
    And Alice is recorded as the creator of "Acme"
    And Alice is recorded as the last editor of "Acme"
    And "Acme" has status "active"

  Scenario: Creating a record is logged as a creation by its creator
    When Alice creates a customer "Acme" with:
      | email | info@acme.test |
    Then the latest change to "Acme" is a creation
    And the latest change to "Acme" was made by Alice

  Scenario: Who created a record cannot be chosen by the person creating it
    Given Bob is a user without any permissions
    When Alice creates a customer "Acme" with:
      | created by | Bob |
    Then it succeeds
    And Alice is recorded as the creator of "Acme"

  Scenario: A record created from another record's page is linked to it
    Given a topic "Billing"
    When Alice creates a customer "Acme" prefilled with topic "Billing"
    Then it succeeds
    And "Acme" has topic "Billing"

  Scenario: Only the fields a type allows can be prefilled
    When Alice creates a customer "Acme" prefilled with status "churned"
    Then it succeeds
    And "Acme" has status "active"

  Scenario: A required field must be filled in
    When Alice creates a customer with:
      | email | hello@acme.test |
    Then it is rejected with "This field is required."

  Scenario: A field only accepts one of its choices
    When Alice creates a customer "Acme" with:
      | status | bankrupt |
    Then it is rejected with "is not a valid choice"
    And no customer "Acme" exists

  Scenario: A record type's own rules are checked before saving
    Given Alice can add exchange rates
    When Alice creates an exchange rate with:
      | currency  | USD        |
      | from date | 2025-02-01 |
      | to date   | 2025-01-01 |
      | rate      | 7.0        |
    Then it is rejected with "End date must be after start date"

  Scenario: Creating a record needs permission to add records of its type
    Given Bob can view customers
    When Bob creates a customer "Acme"
    Then it is forbidden
    And no customer "Acme" exists

  Scenario: A rich text field keeps its formatting
    Given Alice can view and add tickets
    When Alice creates a ticket "Printer broken" with:
      | body | <p>It prints <strong>nothing</strong></p> |
    Then it succeeds
    And "Printer broken" has body "<p>It prints <strong>nothing</strong></p>"
