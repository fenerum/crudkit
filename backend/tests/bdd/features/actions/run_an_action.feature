@endpoint:records.action
Feature: Run an action on a record
  A project can give a record type its own buttons, such as "Mark churned" on
  a customer. Anyone allowed to change the record can run them; the project
  can narrow that further. Every run is recorded so it can be undone.

  Background:
    Given Alice can view and change customers
    And a customer "Acme" with status "active"

  Scenario: Running an action does what it says
    When Alice uses the "Mark churned" action on "Acme"
    Then it succeeds
    And "Acme" has status "churned"

  Scenario: An action that returns the record takes the person to it
    When Alice uses the "Mark churned" action on "Acme"
    Then Alice is taken to "Acme"

  Scenario: An action can send the person to another page
    Given customers have an action "Open billing" that sends people to the billing page
    When Alice uses the "Open billing" action on "Acme"
    Then Alice is sent to the billing page

  Scenario: An action can answer with its own message
    Given customers have an action "Check credit" that answers "Credit OK"
    When Alice uses the "Check credit" action on "Acme"
    Then Alice gets the answer "Credit OK"

 
  Scenario: An action that gives no answer still runs and is recorded
    Given customers have an action "Quietly churn" that sets the status to "churned" and answers nothing
    When Alice uses the "Quietly churn" action on "Acme"
    Then it succeeds
    And "Acme" has status "churned"
    And the latest change to "Acme" is labelled "Quietly churn"

  Scenario: A run is recorded under the action's name with what it changed
    When Alice uses the "Mark churned" action on "Acme"
    Then the latest change to "Acme" is an action
    And the latest change to "Acme" is labelled "Mark churned"
    And the latest change to "Acme" changed the status from "active" to "churned"

  Scenario: Running an action can be undone
    Given Alice used the "Mark churned" action on "Acme"
    When Alice undoes that change
    Then it succeeds
    And "Acme" has status "active"

  Scenario: An action that removes its own record is recorded as a deletion
    Given customers have an action "Erase" that erases the record
    When Alice uses the "Erase" action on "Acme"
    Then it succeeds
    And "Acme" no longer exists and its removal is logged as "Erase"

  Scenario: Each record type only offers its own actions
    When Alice tries the action "escalate" on "Acme"
    Then it is rejected with "Action escalate not found"
    And "Acme" still has status "active"

  Scenario: Other record types run their own actions
    Given Alice can view and change urgent comments
    And a ticket "Printer broken"
    And an urgent comment "Paper jam again" on the ticket "Printer broken"
    When Alice uses the "Escalate" action on "Paper jam again"
    Then it succeeds
    And "Paper jam again" has escalation reason "escalated"

  Scenario: Running an action needs the change permission
    Given Bob can view customers
    When Bob uses the "Mark churned" action on "Acme"
    Then it is forbidden
    And "Acme" still has status "active"

  Scenario: Actions cannot be run on a deleted record
    Given Alice can delete customers
    And Alice deleted "Acme"
    When Alice uses the "Mark churned" action on "Acme"
    Then it is not found
