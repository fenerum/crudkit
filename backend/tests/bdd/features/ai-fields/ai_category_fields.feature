@field:AICategoryField
Feature: AI category fields
  An AI category field lets the AI sort a record into one of a fixed set of
  categories. An answer outside that set is ignored rather than stored, so
  the field only ever holds a category people defined.

  Background:
    Given a ticket "Invoice is wrong"
    And the AI sorts tickets into the categories "billing" and "technical"

  Scenario: The AI's category is stored
    Given the AI picks the category "billing"
    When the AI fields of "Invoice is wrong" are filled in
    Then "Invoice is wrong" is in the AI category "billing"

  Scenario: A category that is not one of the choices is ignored
    Given the AI picks the category "spam"
    When the AI fields of "Invoice is wrong" are filled in
    Then "Invoice is wrong" has no AI category
