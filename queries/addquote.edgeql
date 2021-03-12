SELECT(
INSERT GuildQuote {
    keyword := <bounded_str>$name,
    quote_text := <str>$quote_text,
    created_by := (
        INSERT User {
            discord_id := <std::bigint>$user_id,
            name := <bounded_str>$user_name,
            tag := <bounded_str>$user_tag,
        }
        UNLESS CONFLICT ON .discord_id
        ELSE (
            UPDATE User
            FILTER User.discord_id = <std::bigint>$user_id
            SET {
                name := <bounded_str>$user_name,
                tag := <bounded_str>$user_tag,
            }
        )
    ),
    guild := (
        SELECT Guild
        FILTER discord_id = <std::bigint>$guild_id
        LIMIT 1
    ),
}
UNLESS CONFLICT ON .guild_keyword ELSE (
    SELECT GuildQuote
)
) {
    keyword,
    quote_text,
    created_by: {
        user_id,
        name,
        tag,
        is_owner,
    },
    created_at,
    guild: {
        guild_id,
        name,
    },
}

SELECT (
INSERT GlobalQuote {
    keyword := <bounded_str>$keyword,
    quote_text := <str>$quote_text,
    created_by := (
        INSERT User {
            discord_id := <std::bigint>$user_id,
            name := <bounded_str>$user_name,
            tag := <bounded_str>$user_tag,
            is_owner := True,
        }
        UNLESS CONFLICT ON .discord_id ELSE (
            UPDATE User
            FILTER User.discord_id = <std::bigint>$user_id
            SET {
                is_owner := True,
                name := <bounded_str>$user_name,
                tag := <bounded_str>$user_tag,
            }
        )
    ),
}
UNLESS CONFLICT ON .keyword ELSE (
    SELECT GlobalQuote
)
) {
    keyword,
    quote_text,
    created_by: {
        user_id,
        name,
        tag,
        is_owner,
    },
    created_at,
}

SELECT(
INSERT ChannelQuote {
    keyword := <bounded_str>$name,
    quote_text := <str>$quote_text,
    created_by := (
        INSERT User {
            discord_id := <std::bigint>$user_id,
            name := <bounded_str>$user_name,
            tag := <bounded_str>$user_tag,
        }
        UNLESS CONFLICT ON .discord_id
        ELSE (
            UPDATE User
            
        )
    ),
    guild := (
        SELECT Guild
        FILTER discord_id = <std::bigint>$guild_id
        LIMIT 1
    ),
}
UNLESS CONFLICT ON .guild_keyword ELSE (
    SELECT ChannelQuote
)
) {
    keyword,
    quote_text,
    created_by: {
        discord_id,
        name,
        tag,
        is_owner,
    },
    created_at,
    channel: {
        channel_id,
        name,
    },
}