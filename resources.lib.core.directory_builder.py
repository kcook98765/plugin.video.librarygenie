def build_directory(self, items: List[Dict[str, Any]], view_hint: str = 'default') -> None:
        """Build Kodi directory from list of item dictionaries using factory pattern"""
        try:
            utils.log(f"Building directory with {len(items)} items", "DEBUG")

            for item_data in items:
                try:
                    # Normalize item data to MediaItem
                    media_item = from_db(item_data)

                    # Build ListItem using factory
                    li = build_listitem(media_item, view_hint)

                    # Add to directory
                    xbmcplugin.addDirectoryItem(
                        handle=int(sys.argv[1]),
                        url=media_item.play_path,
                        listitem=li,
                        isFolder=media_item.is_folder
                    )

                except Exception as e:
                    utils.log(f"Error building item {item_data.get('title', 'Unknown')}: {str(e)}", "ERROR")
                    continue

            # End directory
            xbmcplugin.endOfDirectory(int(sys.argv[1]))

        except Exception as e:
            utils.log(f"Error building directory: {str(e)}", "ERROR")
            xbmcplugin.endOfDirectory(int(sys.argv[1]), succeeded=False)