@endpoint:records.partial_update @endpoint:records.action @endpoint:records.bulk @endpoint:records.import
Feature: Celebrate a record reaching a milestone
  A project can mark the moments worth a little party, such as a deal being
  won or a case being closed. When someone moves a record there, the app
  celebrates with a burst of confetti. A project can also have an action
  celebrate when it runs.

  Background:
    Given Alice can view and change customers
    And a customer "Acme" with status "active"
    And customers celebrate reaching status "churned"

  Scenario: Moving a record into a celebrated value celebrates
    When Alice changes the status of "Acme" to "churned"
    Then it succeeds
    And the app celebrates

  Scenario: Moving a record into any other value does not celebrate
    Given customers celebrate reaching status "bankrupt"
    When Alice changes the status of "Acme" to "churned"
    Then it succeeds
    And the app does not celebrate

  Scenario: Saving a record that was already there does not celebrate again
    Given a customer "Beta" with status "churned"
    When Alice changes the status of "Beta" to "churned"
    Then it succeeds
    And the app does not celebrate

  Scenario: An action that moves the record there celebrates
    When Alice uses the "Mark churned" action on "Acme"
    Then it succeeds
    And the app celebrates

  Scenario: Changing many records at once celebrates
    Given a customer "Beta" with status "active"
    When Alice sets the status of "Acme" and "Beta" to "churned" at once
    Then it succeeds
    And the app celebrates

  Scenario: Importing records into a celebrated value celebrates
    Given Alice can view, add and change customers
    When Alice imports a customers sheet:
      | name   | status  |
      | Globex | churned |
    Then it succeeds
    And the app celebrates

  Scenario: Previewing an import does not celebrate
    Given Alice can view, add and change customers
    When Alice previews importing a customers sheet:
      | name   | status  |
      | Globex | churned |
    Then it succeeds
    And the app does not celebrate

  Scenario: Undoing a change back into a celebrated value does not celebrate
    Given Alice changed the status of "Acme" to "churned"
    And Alice changed the status of "Acme" to "active"
    When Alice undoes that change
    Then it succeeds
    And "Acme" has status "churned"
    And the app does not celebrate

  Scenario: An action can ask to celebrate
    Given customers have an action "Ring the bell" that asks to celebrate
    When Alice uses the "Ring the bell" action on "Acme"
    Then it succeeds
    And the app celebrates

  Scenario: A record type that marks no milestones never celebrates
    Given Alice can view and change topics
    And a topic "Billing"
    When Alice changes the name of "Billing" to "Invoices"
    Then it succeeds
    And the app does not celebrate
