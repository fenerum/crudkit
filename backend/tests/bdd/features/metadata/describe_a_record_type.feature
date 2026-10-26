@endpoint:records.metadata
Feature: Describe a record type
  The app builds its forms, columns and pickers from a description of each
  record type: its names, its fields and their rules, which records point at
  it and which actions it offers. Projects get a working form for every
  record type without writing one.

  Background:
    Given Alice can view and add customers
    And Bob can view customers

  Scenario: The description names the record type
    When Alice looks up the description of customers
    Then the description names the type "customer", or "customers" for several
    And the description covers every field of customers

  Scenario: The description says which fields must be filled in
    When Alice looks up the description of customers
    Then the field "name" is required
    And the field "name" holds at most 255 characters
    And the field "email" is optional

  Scenario: The description gives a field's choices and default
    When Alice looks up the description of customers
    Then the field "status" offers the choices "active" and "churned"
    And the field "status" defaults to "active"

  Scenario: The description says which fields link to other records and which are kept by the app
    When Alice looks up the description of customers
    Then the field "topic" links to topics
    And the field "created by" cannot be edited

  Scenario: The description explains a field with its help text
    Given Alice can view layouts
    When Alice looks up the description of layouts
    Then the field "fields" is explained with "Format: [field1, field2, ...]"

  Scenario Outline: The description says whether the person may create records
    When <name> looks up the description of customers
    Then the description says new customers <may> be created

    Examples:
      | name  | may     |
      | Alice | may     |
      | Bob   | may not |

  Scenario: The description says how new records can be prefilled and how they are searched
    When Alice looks up the description of customers
    Then the description lets new records be prefilled with name, email and topic
    And the description says records are searched by name and email
    And the description offers creating new ones from pickers

  Scenario: The description lists the records that point at the record type
    When Alice looks up the description of customers
    Then the description says tickets point at it through "customer"
    And the description says feed items point at it through "parent object"
    And the description says external objects point at it through "related object"

  @known-bug
  Scenario: A one-way link from another record type is not described
    When Alice looks up the description of customers
    Then the description does not say tickets point at it through "watchers"

  Scenario: A project can add its own kinds of records that point at every record
    Given the project also lists work logs on every record
    When Alice looks up the description of customers
    Then the description says work logs point at it through "related object"

  Scenario: The description lists the actions people can run
    When Alice looks up the description of customers
    Then the description offers the action "Mark churned", which needs no approval

  Scenario: The description says which related records a page shows inline by default
    Given customer pages show the subject of their tickets inline by default
    When Alice looks up the description of customers
    Then the description shows the subject of tickets inline by default

  Scenario: Looking up a description needs permission to view the record type
    Given Carol is a user without any permissions
    When Carol looks up the description of customers
    Then it is forbidden
