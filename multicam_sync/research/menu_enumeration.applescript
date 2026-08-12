-- R1: DaVinci Resolve Menu Bar Enumeration
-- Purpose: Discover all accessible menu items, especially under "片段" (Clip) menu
-- Usage: osascript research/menu_enumeration.applescript

set output to ""

tell application "System Events"
	if not (exists process "Resolve") then
		return "ERROR: DaVinci Resolve is not running"
	end if

	tell process "Resolve"
		set frontmost to true
		delay 0.5

		-- Enumerate all menus in the menu bar
		set menuBarItems to every menu bar item of menu bar 1

		set output to output & "=== Resolve Menu Bar Items ===" & return

		repeat with menuBarItem in menuBarItems
			try
				set menuName to name of menuBarItem
				set output to output & return & "MENU: " & menuName & return
				set output to output & "  Title: " & (title of menuBarItem) & return
				set output to output & "  Description: " & (description of menuBarItem) & return
			on error errMsg
				set output to output & "MENU: <unnamed/error: " & errMsg & ">" & return
			end try

			try
				set theMenu to menu 1 of menuBarItem
				set menuItems to every menu item of theMenu
				set output to output & "  Items count: " & (count of menuItems) & return

				repeat with menuItem in menuItems
					try
						set itemName to name of menuItem
						set output to output & "    - " & itemName

						-- Check if this item has a submenu
						try
							set subMenu to menu 1 of menuItem
							set subItems to every menu item of subMenu
							set output to output & " [" & (count of subItems) & " sub-items]"
						on error
							-- No submenu
						end try

						set output to output & return
					on error errMsg
						set output to output & "    - <error: " & errMsg & ">" & return
					end try
				end repeat
			on error errMsg
				set output to output & "  <could not get menu items: " & errMsg & ">" & return
			end try
		end repeat

		-- Now specifically try to click the "片段" menu and enumerate it
		set output to output & return & "=== Detailed: 片段 (Clip) Menu ===" & return
		try
			click menu bar item "片段" of menu bar 1
			delay 0.5

			set clipMenu to menu 1 of menu bar item "片段" of menu bar 1
			set clipItems to every menu item of clipMenu

			repeat with clipItem in clipItems
				try
					set itemName to name of clipItem
					set output to output & "ITEM: " & itemName & return

					-- Check for submenu
					try
						set subMenu to menu 1 of clipItem
						set subItems to every menu item of subMenu
						set output to output & "  Sub-items:" & return
						repeat with subItem in subItems
							try
								set output to output & "    -> " & (name of subItem) & return
							end try
						end repeat
					end try
				end try
			end repeat

			-- Close the menu by pressing Escape
			keystroke (character id 27)
		on error errMsg
			set output to output & "ERROR opening 片段 menu: " & errMsg & return
		end try
	end tell
end tell

return output
