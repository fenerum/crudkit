@type:CHG
Feature: Changes that come from other systems
  Records kept in step with another system (a billing tool, a data warehouse)
  are imported and updated by the system itself. Their history says which
  system the change came from, and a sync that changes nothing leaves no trace.

  Scenario: Importing a new record logs a creation by the system
    When the "billing" system imports its customer "42" as "Acme"
    Then the latest change to "Acme" is a creation
    And the latest change to "Acme" is labelled "Imported from billing"
    And the latest change to "Acme" was made by the system
    And the latest change to "Acme" came from the system
    And "Acme" is linked to the "billing" system as "42"

  Scenario: A sync that changes a record logs what changed
    Given the "billing" system imported its customer "42" as "Acme"
    When the "billing" system renames its customer "42" to "Acme Ltd"
    Then the latest change to "Acme" is an update
    And the latest change to "Acme" is labelled "Updated from billing"
    And the latest change to "Acme" changed the name from "Acme" to "Acme Ltd"
    And the latest change to "Acme" was made by the system

  Scenario: A sync that changes nothing logs nothing
    Given the "billing" system imported its customer "42" as "Acme"
    When the "billing" system sends its customer "42" again unchanged
    Then the change log of "Acme" has 1 entry

  Scenario: Importing a record that already exists logs only what the import changed
    Given a customer "Acme" with email "hello@acme.test"
    When the "billing" system imports its customer "42", which matches "Acme" by email, with the name "Acme A/S"
    Then the latest change to "Acme" is an update
    And the latest change to "Acme" is labelled "Imported from billing"
    And the latest change to "Acme" changed only the name
    And "Acme" is linked to the "billing" system as "42"

  Scenario: A sync that brings a deleted record back is logged as a restore
    Given the "billing" system imported its customer "42" as "Acme"
    And "Acme" has since been deleted
    When the "billing" system marks its customer "42" as not deleted
    Then "Acme" is not deleted
    And the latest change to "Acme" is a restore
    And the latest change to "Acme" is labelled "Updated from billing"
