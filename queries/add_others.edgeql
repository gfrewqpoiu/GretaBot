SELECT(
INSERT User {
    discord_id := <std::bigint>$user_id,
    name := <bounded_str>$user_name,
    tag := <bounded_str>$user_tag,
}
UNLESS CONFLICT ON .discord_id
ELSE (
    UPDATE User
    FILTER .discord_id = <std::bigint>$user_id
    SET {
        name := <bounded_str>$user_name,
        tag := <bounded_str>$user_tag,
    }
)
) {
    id,
    discord_id,
    user_id,
    name,
    tag,
    is_owner,
};

SELECT(
INSERT Guild {
    discord_id := <std::bigint>$guild_id,
    name := <std::bigint>$guild_name,
    users := $users,
}
UNLESS CONFLICT ON .discord_id
ELSE (
    UPDATE Guild
    FILTER .discord_id = $guild_id
    SET {
        name := <std::bigint>$guild_name,
        users := $users,
    }
)
) {
    id,
    discord_id,
    guild_id,
    name,
    channels: {
        discord_id,
        channel_id,
        name,
    },
    users: {
        discord_id,
        user_id,
        name,
        tag,
        is_owner,
    },
};

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