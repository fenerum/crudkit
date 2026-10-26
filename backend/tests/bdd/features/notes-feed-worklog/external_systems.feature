@type:EXT
Feature: Records linked to external systems
  Integrations keep CrudKit in sync with outside systems such as billing. A
  record remembers its id in each outside system, so the next sync updates
  the same record instead of creating a duplicate, and the change log says
  which system made each change.

  Scenario: The first import creates the record and links it
    When the "billing" system imports customer "42" named "Initech"
    Then "42" in the "billing" system is linked to "Initech"
    And the latest change to "Initech" is a creation
    And the latest change to "Initech" is labelled "Imported from billing"
    And the latest change to "Initech" was made by the system

  Scenario: The next import updates the same record
    Given the "billing" system imported customer "42" named "Initech"
    When the "billing" system imports customer "42" named "Initech Corp"
    Then "Initech" has name "Initech Corp"
    And the latest change to "Initech" is labelled "Updated from billing"

  Scenario: An import that changes nothing is not logged
    Given the "billing" system imported customer "42" named "Initech"
    When the "billing" system imports customer "42" named "Initech"
    Then the change log of "Initech" has 1 entry

  Scenario: An import can adopt a record that already exists
    Given a customer "Acme" with email "ap@acme.test"
    When the "billing" system imports customer "7" named "Acme Corp", matching on email "ap@acme.test"
    Then "7" in the "billing" system is linked to "Acme"
    And "Acme" has name "Acme Corp"

  Scenario: A record is looked up by its id in the outside system
    Given a customer "Acme"
    And "Acme" is linked to "42" in the "billing" system
    Then looking up customer "42" in the "billing" system finds "Acme"
    And looking up customer "43" in the "billing" system finds nothing
    And looking up customer "42" in the "crm" system finds nothing

  Scenario: The same outside id can belong to records of different types
    Given a customer "Acme"
    And a topic "Sales"
    And "Acme" is linked to "42" in the "billing" system
    And "Sales" is linked to "42" in the "billing" system
    Then looking up customer "42" in the "billing" system finds "Acme"
    And looking up topic "42" in the "billing" system finds "Sales"

  Scenario: An outside id links to only one record of a type
    Given a customer "Acme"
    And a customer "Globex"
    And "Acme" is linked to "42" in the "billing" system
    Then linking "Globex" to "42" in the "billing" system is refused
