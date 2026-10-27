@field:WYSIWYGEditorField @field:EmailWYSIWYGEditorField @field:ModelField @field:FieldChoiceField
Feature: Special kinds of fields
  Besides plain text, numbers and links, CrudKit offers a few kinds of fields
  that tell the app which editor to show: rich text, email bodies, a choice of
  record type and a choice of field. Projects use them on their own record
  types and the forms follow.

  Background:
    Given Alice is a superuser

  Scenario: A rich text field is described as rich text
    When Alice looks up the description of tickets
    Then the field "body" is described as rich text
    And the field "body" is optional

  Scenario: An email body field is described as such
    Given customers also have a field "signature" made for email bodies
    When Alice looks up the description of customers
    Then the field "signature" is described as email bodies

  Scenario: A record type field offers every record type as a choice
    When Alice looks up the description of layouts
    Then the field "model" is described as choosing a record type
    And the field "model" offers every record type as a choice
    And the field "model" holds at most 3 characters

  Scenario: A field choice field holds the name of a field
    Given customers also have a field "sort field" made for choosing a field
    When Alice looks up the description of customers
    Then the field "sort field" is described as choosing a field
    And the field "sort field" holds at most 128 characters
