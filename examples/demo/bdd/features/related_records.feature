@page:/<segment>/create
Feature: Related records
  A record's page lists the records that point to it, and a form can create a
  missing related record on the spot, so nobody has to abandon a half-filled
  form to go and add something first.

  Background:
    Given Alice is signed in

  Scenario: An author's books are listed on a tab of the author's page
    When Alice opens the books tab of "Ursula K. Le Guin"
    Then she sees "The Left Hand of Darkness" and "The Dispossessed"
    But she does not see "Kindred"

  Scenario: A book added from the tab already has its author filled in
    Given an author "Debut author"
    When Alice opens the books tab of "Debut author"
    And she adds a new one from the tab
    Then the form shows "Debut author"
    When she fills in the name "Late discovery"
    And she creates it
    And she opens the books tab of "Debut author"
    Then she sees "Late discovery"

  Scenario: A missing book and author are created without leaving the form
    Given Alice is filling in a new reading
    When she fills in the name "Holiday read"
    And she creates the book "First edition" on the spot
    And she creates the author "New voice" on the spot
    And she creates it
    Then the form shows "New voice"
    When she creates it
    Then the form shows "First edition"
    And the form still has the name "Holiday read"
    When she creates it
    Then she is on the page of a new reading
    And she sees the link "First edition"

  Scenario: What was typed before creating a related record is kept
    Given Alice is filling in a new reading
    When she creates the book "First edition" on the spot
    And she fills in the name "First edition, signed"
    And she creates the author "New voice" on the spot
    And she creates it
    Then the form has the name "First edition, signed"

  Scenario: Escape closes only the innermost form
    Given Alice is filling in a new reading
    When she creates the book "First edition" on the spot
    And she creates the author "New voice" on the spot
    And she presses Escape
    Then only the form for the book is still open

  Scenario: Enter saves only the innermost form
    Given Alice is filling in a new reading
    When she creates the book "First edition" on the spot
    And she creates the author "New voice" on the spot
    And she presses Enter
    Then only the form for the book is still open
    And the form shows "New voice"
