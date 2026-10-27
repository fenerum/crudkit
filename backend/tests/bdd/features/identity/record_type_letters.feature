@check:crudkit.E001 @check:crudkit.E002
Feature: Every record type has its own three letters
  The letters in front of a record's number tell which type of record it is,
  so every record type must declare exactly three capital letters and no two
  types may share them. Django's system checks report a project that breaks
  this before it starts serving.

  Scenario: The record types of a correctly set up project pass the check
    When the record types are checked
    Then the record type check passes

  Scenario Outline: A record type whose letters are not three capitals is reported
    Given the record type topic declares the letters "<letters>"
    When the record types are checked
    Then the record type check fails with "crudkit.E001" saying "must define TYPE_ID as three uppercase letters"

    Examples:
      | letters |
      | top     |
      | TO      |
      | TOPS    |
      | T0P     |

  Scenario: A record type without letters is reported
    Given the record type topic declares no letters
    When the record types are checked
    Then the record type check fails with "crudkit.E001" saying "testapp.Topic must define TYPE_ID"

  Scenario: Two record types with the same letters are reported
    Given the record type topic declares the letters "CUS"
    When the record types are checked
    Then the record type check fails with "crudkit.E002" saying "TYPE_ID 'CUS' is used by multiple models"

  Scenario: A record of a type without letters cannot be made
    Given the record type topic declares no letters
    When a new record of that type is made
    Then making it fails with "Please define TYPE_ID on the BaseCrudKitModel"
