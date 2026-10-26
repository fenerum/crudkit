@endpoint:records.retrieve
Feature: Open a record
  Opening a record shows all of its fields, a readable label, and the records
  it links to with enough detail to show them without asking again. Secrets
  such as passwords are never shown.

  Background:
    Given Alice can view customers
    And a topic "Billing"
    And a customer "Acme" with topic "Billing"

  Scenario: Opening a record shows it with its label
    When Alice looks at "Acme"
    Then the record shown is "Acme"
    And "Acme" has status "active"

  Scenario: A linked record is shown along with the record
    When Alice looks at "Acme"
    Then the topic is shown as "Billing"

  Scenario: The people who created and changed a record are shown without their passwords
    When Alice looks at "Acme"
    Then the people on the record are shown without their passwords

  Scenario: Lists of linked records are not part of an opened record
    Given Alice can view tickets
    And a ticket "Printer broken"
    When Alice looks at "Printer broken"
    Then the record shown is "Printer broken"
    And the record does not include the watchers

  Scenario: A deleted record can no longer be opened
    Given Alice can delete customers
    And Alice deleted "Acme"
    When Alice looks at "Acme"
    Then it is not found

  Scenario: A deleted record can still be opened when asked for
    Given Alice can delete customers
    And Alice deleted "Acme"
    When Alice opens the deleted "Acme"
    Then the record shown is "Acme"

  Scenario: Opening a record needs permission to view its type
    Given Bob is a user without any permissions
    When Bob looks at "Acme"
    Then it is forbidden

  Scenario: Opening a record needs signing in
    When someone who is not signed in looks at "Acme"
    Then it requires signing in
