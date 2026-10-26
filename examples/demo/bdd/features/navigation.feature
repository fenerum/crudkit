@page:/all-objects @page:not-found
Feature: Finding your way around
  Every kind of record has its own list, and the overview of all record
  types links to each of them. A broken or outdated link says so instead of
  showing an empty screen.

  Background:
    Given Alice is signed in

  Scenario: The overview lists every kind of record
    When Alice opens the overview of all record types
    Then she sees "books", "authors" and "readings"

  Scenario: The overview leads to the list of a record type
    When Alice opens the overview of all record types
    And she follows the link "books"
    Then she is on the books list

  Scenario: A page that does not exist says so and leads home
    When Alice opens a page that does not exist
    Then she sees "Page not found"
    When she follows the link "Go home"
    Then she is on the dashboard
