@page:/<segment>/create @page:/<segment>/edit @page:/<segment>/delete
Feature: Managing books
  Adding, correcting and removing records happens in forms generated from
  the record type, so a new kind of record needs no screens of its own.

  Background:
    Given Alice is signed in

  Scenario: A new book is added from the list and can be found in it
    Given Alice is on the books list
    When she starts a new book
    And she fills in the name "Unwritten"
    And she picks "Italo Calvino" as the author
    And she creates it
    Then she is on the books list
    When she searches the list for "Unwritten"
    Then the list has 1 record

  Scenario: A book's page links to its author
    Given a book "Unwritten" with author "Italo Calvino"
    When Alice opens "Unwritten"
    Then she sees "Unwritten"
    And she sees the link "Italo Calvino"

  Scenario: The edit form starts from the book as it is
    Given a book "Unwritten" with author "Italo Calvino"
    When Alice edits "Unwritten"
    Then the form has the name "Unwritten"

  Scenario: Saving an edit returns to the book with the change
    Given a book "Unwritten" with author "Italo Calvino"
    When Alice edits "Unwritten"
    And she fills in the name "Unwritten, revised"
    And she saves it
    Then she is on the page of "Unwritten"
    And she sees "Unwritten, revised"

  Scenario: A deleted book is gone from the list
    Given a book "Unwritten" with author "Italo Calvino"
    When Alice deletes "Unwritten"
    And she searches the books list for "Unwritten"
    Then the list is empty
