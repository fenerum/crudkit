@page:/<segment>
Feature: Lists
  Every record type has a list that can be searched and paged through, so
  any record is a few keystrokes away however many there are.

  Background:
    Given Alice is signed in

  Scenario: The list shows the records
    When Alice opens the books list
    Then she sees "The Left Hand of Darkness" and "Parable of the Sower"

  Scenario: Searching narrows the list
    When Alice searches the books list for "Kindred"
    Then she sees "Kindred"
    But she does not see "The Dispossessed"
    And the list has 1 record

  Scenario: A search survives reloading the page
    When Alice searches the books list for "Kindred"
    And she reloads the page
    Then she does not see "The Dispossessed"
    And the list has 1 record

  Scenario: Next and Previous move one page at a time
    Given Alice pages through the authors one at a time
    When she goes to the next page
    Then the list is on page 2
    When she goes to the previous page
    Then the list is on page 1

  Scenario: A nearby page can be picked by its number
    Given Alice pages through the authors one at a time
    When she goes to the next page
    And she goes to page 3
    Then the list is on page 3

  Scenario: There is no page before the first or after the last
    Given Alice pages through the authors one at a time
    Then there is no previous page
    When she goes to the last page
    Then there is no next page

  Scenario: The chosen page size is remembered
    Given Alice is on the readings list
    When she shows 10 records per page
    Then the list shows 10 records per page
    When she opens the readings list
    Then the list shows 10 records per page
