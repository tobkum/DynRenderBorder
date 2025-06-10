# Dynamic Render Border for Blender

## Overview

Dynamic Render Border is a Blender addon that automatically adjusts the render border to fit around selected objects or objects within specified collections. This is particularly useful for optimizing render times by ensuring that only the necessary parts of your scene are rendered, especially during animations or when focusing on specific elements.

## Features

*   **Automatic Border Adjustment:** The render border dynamically updates to frame the target objects.
*   **Target Modes:**
    *   **Object List:** Specify individual mesh objects to be included in the render border.
    *   **Collection List:** Specify collections; all mesh objects within these collections (and their sub-collections) will be considered.
*   **Padding Control:** Add adjustable padding around the calculated border.
*   **Automatic Updates:** The border updates automatically on frame changes when enabled.
*   **Manual Update:** A button to manually refresh the render border at any time.
*   **Enable/Disable:** Easily toggle the dynamic border functionality.
*   **User-Friendly UI:** All controls are accessible via a panel in the 3D Viewport's UI sidebar.

## How to Use

1.  **Installation:**
    *   **AWAITING REVIEW ON THE EXTENSIONS PLATFORM, IN THE MEAN TIME:**
    *   Download the addon (usually as a `.zip` file).
    *   In Blender, go to `Edit > Preferences > Get Extensions`.
    *   Click `Install from Disk` under the dropdown in the top right corner and navigate to the downloaded `.zip` file.
    *   Enable the addon by checking the box next to its name ("Dynamic Render Border").

2.  **Accessing the Panel:**
    *   The addon's panel can be found in the 3D Viewport.
    *   Press `N` to open the sidebar (if it's not already open).
    *   Look for a tab named "DynBorder".

3.  **Workflow:**
    *   **Enable:** In the "DynBorder" panel, check the "Enable Dynamic Border" box.
    *   **Choose Target Source:**
        *   **Object List:**
            1.  Select the mesh objects you want to frame in the 3D View.
            2.  Click the "+" (Add Selected to Object List) button in the panel.
            3.  You can remove objects or clear the list using the respective buttons.
        *   **Collection List:**
            1.  Use the eyedropper or search field under "Collection to Add" to pick a collection.
            2.  Click the "+" (Add Collection to List) button.
            3.  You can remove collections or clear the list using the respective buttons.
    *   **Adjust Padding:** Modify the "Padding" slider to add space around the objects within the render border.
    *   **Update:**
        *   The render border will update automatically when you change frames (if animation is playing or scrubbing).
        *   Click "Update Border Now" for an immediate manual update.

4.  **Rendering:**
    *   Ensure you have an active camera in your scene.
    *   When you render, Blender will use the dynamically adjusted render border. If no valid targets are found or they are off-screen, the render border will be disabled automatically.

## Notes

*   The addon currently only considers **MESH** objects for bounding box calculations.
*   Objects must be visible in the viewport and render (`visible_get()` and `hide_viewport == False`) to be included.
*   An active camera is required for the addon to function correctly.

---

This addon helps streamline workflows where you need to focus renders on specific, changing parts of your scene.
