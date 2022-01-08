SELECT(
    INSERT GuildChannel {
        discord_id := <std::bigint>$channel_id,
        name := <bounded_str>$channel_name,
        guild := (
            SELECT Guild
            FILTER discord_id = <std::bigint>$guild_id
            LIMIT 1
        )
    }
    UNLESS CONFLICT ON .discord_id ELSE (
        UPDATE GuildChannel
        FILTER .discord_id = <std::bigint>$channel_id
        SET {
            name := <bounded_str>$channel_name,
        }
    )
) {
    id,
    discord_id,
    channel_id,
    name,
    guild: {
        discord_id,
        guild_id,
        name,
        users: {
            discord_id,
            name,
            tag,
            is_owner,
    },
    channels: {
        discord_id,
        channel_id,
        name,
    }, 
};