@type:SNP
Feature: Snippets of reusable text
  Snippets are pieces of text people insert again and again, like a greeting
  or a sign-off. A snippet can be meant for some record types only, and
  snippets are found by their name.

  Background:
    Given Alice can view and add snippets

  Scenario: A snippet is meant for every record type unless limited
    When Alice saves the snippet "Sign-off" with "Best regards"
    Then it succeeds
    And the snippet "Sign-off" is not limited to any record type

  Scenario: A snippet can be limited to some record types
    When Alice saves the snippet "Greeting" with "Hello there" for customers and tickets
    Then it succeeds
    And the snippet "Greeting" is meant for customers and tickets

  Scenario: Snippets are found by their name
    Given a snippet "Greeting" with body "Hello there"
    And a snippet "Sign-off" with body "Best regards"
    When Alice searches the snippets for "greet"
    Then the list holds only "Greeting"
