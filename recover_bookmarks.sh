#recover bookmarks from a clips object
echo "["
cat clips.json | jq -c '.clips[]' | while IFS= read -r obj; do
    echo "$obj"| jq -r '.start'
    echo ","
    echo "$obj"| jq -r '.end'
    echo ","
done
echo "]"