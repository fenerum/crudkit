Feature: Describe one record to the assistant
  Before the assistant proposes a change, it reads a description of the
  record: the fields it may change with their current values and the values
  they accept, the actions it can run and the records that point at it. Only
  what the person it works for may see is offered.

  Background:
    Given Alice can view customers
    And Alice can view tickets
    And a customer "Acme" with status "active"
    And a customer "Globex"
    And a ticket "Printer broken" with customer "Acme"

  Scenario: The description gives the current value of each field that can be changed
    When the assistant describes "Printer broken" for Alice
    Then the record description gives the subject as "Printer broken"
    And the record description gives the customer as "Acme"
    And the record description leaves out id, created by, updated by, created at, updated at and deleted

  Scenario: A field with fixed choices offers them
    When the assistant describes "Acme" for Alice
    Then the record description offers "active" and "churned" as the choices for status

  Scenario: A link offers the records the person may see, leaving out deleted ones
    Given Alice can delete customers
    And a customer "Initech"
    And Alice deleted "Initech"
    When the assistant describes "Printer broken" for Alice
    Then the record description offers "Acme" and "Globex" as the choices for customer

  Scenario: A link offers nothing the person may not see
    Given Bob can view tickets
    When the assistant describes "Printer broken" for Bob
    Then the record description offers no choices for customer

  Scenario: A link to a long list of records says so instead of listing them
    Given 50 customers named "Customer" followed by a number
    When the assistant describes "Printer broken" for Alice
    Then the record description says there are too many customers to list for customer

  Scenario: The description counts the records pointing at the record
    Given a ticket "Invoice missing" with customer "Acme"
    When the assistant describes "Acme" for Alice
    Then the record description counts 2 tickets pointing at it

  Scenario: The description names the actions that can be run
    When the assistant describes "Acme" for Alice
    Then the record description offers the action "mark_churned"
