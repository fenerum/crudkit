Feature: Rules that limit which records a person gets
  On top of the per-type permissions, a project can add rules that decide,
  record by record, what each person may see, change or run actions on, for
  example "sales reps only see their own region". Rules apply everywhere the
  record is reached; superusers are never limited by them.

  Background:
    Given Bob can view and change customers
    And a customer "Acme" with status "active"
    And a customer "Globex" with status "churned"

  Scenario: A rule hides the records it leaves out of the list
    Given people may only get customers with status "active"
    When Bob looks at the list of customers
    Then the list holds only "Acme"

  Scenario: A record hidden by a rule cannot be opened
    Given people may only get customers with status "active"
    When Bob looks at "Globex"
    Then it is not found

  Scenario: A record hidden by a rule cannot be changed
    Given people may only get customers with status "active"
    When Bob changes the name of "Globex" to "Globex Inc"
    Then it is not found
    And "Globex" still has name "Globex"

  Scenario: Superusers are not limited by rules
    Given Alice is a superuser
    And people may only get customers with status "active"
    When Alice looks at the list of customers
    Then the list holds "Acme" and "Globex"

  Scenario: A rule can allow reading a record but not changing it
    Given people may only change the customers they are the owner of
    And the owner of "Acme" is "Bob"
    When Bob looks at "Globex"
    Then it succeeds
    When Bob changes the name of "Globex" to "Globex Inc"
    Then it is not found
    When Bob changes the name of "Acme" to "Acme Inc"
    Then it succeeds

  Scenario: A rule can keep an action to some people
    Given Alice is a superuser
    And only superusers may run "Mark churned" on customers
    When Bob uses the "Mark churned" action on "Acme"
    Then it is forbidden
    And "Acme" still has status "active"
    When Alice uses the "Mark churned" action on "Acme"
    Then it succeeds
    And "Acme" has status "churned"
