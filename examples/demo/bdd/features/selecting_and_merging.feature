@page:/<segment>/merge
Feature: Selecting and merging records
  Several records can be selected in a list to act on them together. Two
  records that turn out to be the same thing can be merged into one, keeping
  the best value of each field.

  Background:
    Given Alice is signed in
    And a book "Twin" with author "Octavia E. Butler"
    And a book "Twin copy" with author "Octavia E. Butler"
    And a book "Twin draft" with author "Octavia E. Butler"

  Scenario: A single selected record cannot be merged
    When Alice selects "Twin" in the books list
    Then the bulk bar shows 1 selected
    And the bulk bar does not offer to merge

  Scenario: Every record on the page can be selected at once
    When Alice selects "Twin" in the books list
    And she selects everything on the page
    Then the bulk bar shows 3 selected

  Scenario: The bulk bar counts the selected records
    When Alice selects "Twin", "Twin copy" and "Twin draft" in the books list
    Then the bulk bar shows 3 selected
    When she unselects "Twin draft"
    Then the bulk bar shows 2 selected
    And the bulk bar offers to merge "Twin" and "Twin copy"

  Scenario: Merging keeps the first record's values unless told otherwise
    When Alice merges "Twin" and "Twin copy" from the books list
    Then the merge keeps "Twin" by default

  Scenario: Merging keeps the chosen values on the first record
    When Alice merges "Twin" and "Twin copy" from the books list
    And she keeps "Twin copy" as the name
    And she completes the merge
    Then she is on the page of "Twin"
    And she sees "Twin copy"
    And "Twin copy" is gone from the books list
