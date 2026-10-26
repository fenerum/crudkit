@page:/<segment>/VIW/<view>
Feature: View layouts
  Besides a plain list, a saved view can lay its records out as a board of
  columns, a gallery of cards, a chart, lanes or a conversation inbox, each
  suited to a different way of working through them.

  Background:
    Given Alice is signed in

  @layout:kanban
  Scenario: A board groups cards into a column per status
    When Alice opens the view "Board" of the readings
    Then the "To read" column holds "Anarchist utopia"
    And the "Reading" column holds "Sower for school"
    And the "Finished" column holds "Book club: Kindred"
    And the card "Anarchist utopia" shows its priority "High"

  @layout:kanban
  Scenario: Dragging a card to another column changes its status
    Given a reading "Drag me" with status "Reading"
    When Alice opens the view "Board" of the readings
    And she drags "Drag me" to the "Finished" column
    Then she is told "Status updated"
    When she reloads the page
    Then the "Finished" column holds "Drag me"

  @layout:kanban
  Scenario: Dragging a card within a column changes the order
    Given a reading "Order first" with:
      | status     | Reading |
      | sort order | 1000    |
    And a reading "Order second" with:
      | status     | Reading |
      | sort order | 1001    |
    When Alice opens the view "Board" of the readings
    And she drags "Order second" above "Order first"
    And she reloads the page
    Then "Order second" comes before "Order first" in the "Reading" column

  @layout:kanban
  Scenario: A card added to a column starts in that column
    When Alice opens the view "Board" of the readings
    And she adds a card to the "Finished" column
    Then the form shows "Finished"
    When she fills in the name "Added from the board"
    And she creates it
    Then the "Finished" column holds "Added from the board"

  @layout:gallery
  Scenario: A gallery card shows the record's second field
    When Alice opens the view "Covers" of the readings
    Then the card "Anarchist utopia" is labelled "To read"

  @layout:gallery
  Scenario: A gallery can be narrowed to one choice
    When Alice opens the view "Covers" of the readings
    And she narrows the gallery to "Finished"
    Then she sees the card "Book club: Kindred"
    But she does not see the card "Anarchist utopia"
    When she narrows the gallery to "All"
    Then she sees the card "Anarchist utopia"

  @layout:quadrant
  Scenario: A chart plots two numbers against each other and links to the records
    When Alice opens the view "Pages vs rating" of the readings
    Then the chart plots pages against rating
    And she sees "Visionaries", "Leaders", "Niche" and "Challengers"
    When she picks "Cities on the train" from the chart's table
    Then she is on the page of "Cities on the train"

  @layout:swimlane
  Scenario: Lanes split each status column by priority
    When Alice opens the view "Lanes" of the readings
    Then the lanes are split by priority
    And the "High" lane holds "Anarchist utopia"
    And the "Low" lane holds "Traveller, again"
    But the "High" lane does not hold "Traveller, again"

  @layout:swimlane
  Scenario: Lanes without totals show no totals
    When Alice opens the view "Lanes" of the readings
    Then the "High" lane holds "Anarchist utopia"
    But she does not see "Grand total" and "DKK"

  @layout:conversation
  Scenario: A conversation inbox opens the picked conversation
    Given a reading "Chat one"
    And a reading "Chat two"
    And a conversation view "Chats" of the readings
    When Alice opens the view "Chats" of the readings
    Then the conversations include "Chat one" and "Chat two"
    When she picks the conversation "Chat one"
    Then the conversation "Chat one" is open
