@type:CHG
Feature: Who made a change
  Every change to a record is logged with who made it and where it came from:
  the app, a script using the API, an undo or the system itself. Support and
  auditors can then tell a person's edit from a nightly sync, and everything
  one save changed is grouped into a single change set that can be undone together.

  Background:
    Given Alice can view and change customers
    And a customer "Acme" with status "active"

  Scenario: A change made in the app is attributed to the person and the app
    When Alice changes the status of "Acme" to "churned"
    Then it succeeds
    And the latest change to "Acme" came from the app
    And the latest change to "Acme" was made by Alice

  @known-bug
  Scenario: Deleting a record in the app records the person as its last editor
    Given Alice can delete customers
    When Alice deletes "Acme"
    Then it succeeds
    And Alice is recorded as the last editor of "Acme"

  Scenario: A change made in a signed-in browser session counts as the app
    When Alice changes the status of "Acme" to "churned" in her browser
    Then it succeeds
    And the latest change to "Acme" came from the app

  Scenario: A change made by a script is attributed to the API and the script's name
    When Alice changes the status of "Acme" to "churned" from the script "nightly-sync"
    Then it succeeds
    And the latest change to "Acme" came from the script "nightly-sync"
    And the latest change to "Acme" was made by Alice

  Scenario: A script that does not give its name is still attributed to the API
    When Alice changes the status of "Acme" to "churned" from a script that does not give its name
    Then it succeeds
    And the latest change to "Acme" came from the API

  Scenario: A very long script name is cut to 255 characters
    When Alice changes the status of "Acme" to "churned" from a script whose name is 300 characters long
    Then it succeeds
    And the latest change to "Acme" came from the API with a script name of 255 characters

  Scenario: Changes made outside any request are attributed to the system
    When a background job changes the status of "Acme" to "churned"
    Then the latest change to "Acme" came from the system
    And the latest change to "Acme" was made by the system

  Scenario: Every change made outside a request gets its own change set
    Given a background job changed the status of "Acme" to "churned"
    When a background job changes the status of "Acme" to "active"
    Then the last 2 changes to "Acme" each have their own change set

  Scenario: The app is told which change set its save made
    When Alice changes the status of "Acme" to "churned"
    Then the app is told the change set of the latest change to "Acme"

  Scenario: Looking at a record makes no change set
    When Alice looks at "Acme"
    Then it succeeds
    And the app is told no change set

  Scenario: A refused change makes no change set
    Given Bob can view customers
    When Bob changes the status of "Acme" to "churned"
    Then it is forbidden
    And the app is told no change set
    And the change log of "Acme" has 0 entries

  Scenario: An undo from the app is logged as an undo, in the change set the app is told about
    Given Alice changed the status of "Acme" to "churned"
    When Alice undoes that change
    Then it succeeds
    And the latest change to "Acme" came from an undo
    And the latest change to "Acme" was made by Alice
    And the app is told the change set of the latest change to "Acme"

  Scenario: An undo run by a script keeps the script's name
    Given Alice changed the status of "Acme" to "churned"
    When Alice undoes that change from the script "cleanup"
    Then it succeeds
    And the latest change to "Acme" came from an undo by the script "cleanup"
