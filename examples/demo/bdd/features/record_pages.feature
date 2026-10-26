@page:/<segment>
Feature: Record pages
  A record's page shows its fields in a readable form and links to the
  records it refers to, so related information is one click away.

  Background:
    Given Alice is signed in

  Scenario: A book opened from the list shows its details
    When Alice searches the books list for "Kindred"
    And she opens "Kindred" from the list
    Then she is on the page of "Kindred"
    And she sees "Jun 1, 1979"

  Scenario: Following the author link opens the author
    When Alice opens "Kindred"
    And she follows the link "Octavia E. Butler"
    Then she is on the page of "Octavia E. Butler"
    And the page is about "Octavia E. Butler"

  Scenario: A choice is shown by its label
    Given a reading "Weekend read"
    When Alice opens "Weekend read"
    Then its status is "To read"
