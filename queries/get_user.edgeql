SELECT User {
    id,
    discord_id,
    user_id,
    name,
    discriminator,
    full_tag,
    is_owner,
    guilds: {
        name,
        discord_id,
    }
}
FILTER User.discord_id = <std::bigint>$discord_id